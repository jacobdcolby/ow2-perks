import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
from urllib.parse import urlparse, unquote

def scrape_overwatch_perks():
    # URL of the Overwatch perks wiki page
    url = "https://overwatch.fandom.com/wiki/Perks"
    
    # Send a GET request to the URL
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code != 200:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")
        return None
    
    # Parse the HTML content
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Initialize a list to store all perk data
    all_perks = []
    
    # Process each role section (Tanks, Damage, Support)
    role_sections = ['Tanks', 'Damage', 'Support']
    
    # Dictionary to store hero icons
    hero_icons = {}
    
    for role in role_sections:
        # Find the section header for this role
        role_header = soup.find('span', {'id': role})
        
        if not role_header:
            print(f"Could not find section for {role}")
            continue
            
        # Based on the HTML structure, find the table after the header
        # Navigate to the h3 containing the role header
        role_h3 = role_header.parent
        
        # Find the next table after this h3
        role_table = role_h3.find_next('table', {'class': 'wikitable'})
        
        if not role_table:
            print(f"Could not find table for {role}")
            continue
            
        # Process the table rows
        rows = role_table.find_all('tr')[1:]  # Skip the header row
        
        # Keep track of the current hero when processing rows with rowspan
        current_hero = None
        current_hero_icon = ""
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 3:  # Skip rows without enough data
                continue
            
            try:
                # Check if this row has a hero cell (the first cell might be missing due to rowspan)
                hero_cell = cells[0] if len(cells) >= 4 else None
                
                # If we have a hero cell with content, update the current hero
                if hero_cell and hero_cell.find('b'):
                    hero_name_elem = hero_cell.find('b')
                    if hero_name_elem.find('a'):
                        current_hero = hero_name_elem.find('a').get_text().strip()
                    else:
                        current_hero = hero_name_elem.get_text().strip()
                    
                    # Try to extract hero icon
                    hero_img = hero_cell.find('img')
                    if hero_img:
                        # Check for data-src first (used for lazy-loaded images)
                        if 'data-src' in hero_img.attrs:
                            current_hero_icon = hero_img['data-src']
                        # Then check regular src
                        elif 'src' in hero_img.attrs:
                            current_hero_icon = hero_img['src']
                        
                        # Skip placeholder/transparent images
                        if 'data:image/gif' in current_hero_icon:
                            # Look for original image URL
                            if 'data-image-key' in hero_img.attrs:
                                img_key = hero_img['data-image-key']
                                # Construct a more reliable URL for the image
                                current_hero_icon = f"https://static.wikia.nocookie.net/overwatch_gamepedia/images/{img_key[0]}/{img_key[0:2]}/{img_key}/revision/latest/scale-to-width-down/50"
                        
                        # Store hero icon URL
                        hero_icons[current_hero] = current_hero_icon
                
                # Determine the indices for perk data based on whether we have a hero cell
                perk_idx = 0 if len(cells) < 4 else 1
                type_idx = perk_idx + 1
                desc_idx = type_idx + 1
                
                # Try different methods to extract perk name
                perk_name = ""
                
                # Method 1: Look for a link with title attribute
                perk_link = cells[perk_idx].find('a', title=True)
                if perk_link:
                    perk_name = perk_link.get_text().strip()
                
                # Method 2: If still empty, try to extract from the last text child of the cell
                if not perk_name:
                    # Find the last text node after all the images and elements
                    for content in cells[perk_idx].contents[::-1]:
                        if isinstance(content, str) and content.strip():
                            perk_name = content.strip()
                            break
                
                # Method 3: If still empty, try to get from the link's title
                if not perk_name and perk_link and 'title' in perk_link.attrs:
                    parts = perk_link['title'].split('#')
                    if len(parts) > 1:
                        perk_name = parts[1].replace('_', ' ')
                
                # If still no perk name, use full cell text and clean it up
                if not perk_name:
                    raw_text = cells[perk_idx].get_text().strip()
                    perk_name = re.sub(r'\s+', ' ', raw_text).strip()
                
                # Extract perk tier (Major/Minor)
                perk_tier = cells[type_idx].get_text().strip()
                
                # Extract perk description
                perk_description = cells[desc_idx].get_text().strip()
                
                # Try to extract icon URL - handle both src and data-src attributes for lazy-loaded images
                icon_element = cells[perk_idx].find('img')
                icon_url = ""
                
                if icon_element:
                    # Check for data-src first (used for lazy-loaded images)
                    if 'data-src' in icon_element.attrs:
                        icon_url = icon_element['data-src']
                    # Then check regular src
                    elif 'src' in icon_element.attrs:
                        icon_url = icon_element['src']
                    
                    # Skip placeholder/transparent images
                    if 'data:image/gif' in icon_url:
                        # Look for original image URL
                        if 'data-image-key' in icon_element.attrs:
                            img_key = icon_element['data-image-key']
                            # Construct a more reliable URL for the image
                            icon_url = f"https://static.wikia.nocookie.net/overwatch_gamepedia/images/{img_key[0]}/{img_key[0:2]}/{img_key}/revision/latest/scale-to-width-down/50"
                
                # Add to our list
                all_perks.append({
                    'Role': role,
                    'Hero': current_hero,
                    'Tier': perk_tier,
                    'Perk Name': perk_name,
                    'Description': perk_description,
                    'Icon URL': icon_url,
                    'Hero Icon URL': hero_icons.get(current_hero, "")
                })
                    
            except Exception as e:
                print(f"Error processing row: {e}")
    
    # Convert to a DataFrame
    perks_df = pd.DataFrame(all_perks)
    
    return perks_df

def download_images(dataframe):
    """Download all perk icons and hero icons to local directories"""
    
    # Create directories if they don't exist
    os.makedirs('perk_icons', exist_ok=True)
    os.makedirs('hero_icons', exist_ok=True)
    
    # Keep track of downloaded images
    local_perk_paths = []
    local_hero_paths = []
    
    # First check what we already have
    existing_perk_icons = set(os.listdir('perk_icons')) if os.path.exists('perk_icons') else set()
    existing_hero_icons = set(os.listdir('hero_icons')) if os.path.exists('hero_icons') else set()
    
    # Track heroes we've already processed to avoid duplicates
    processed_heroes = set()
    
    for i, row in dataframe.iterrows():
        # Process perk icon
        icon_url = row['Icon URL']
        if not icon_url:
            local_perk_paths.append("")
        else:
            try:
                # Create a unique filename using hero name and perk name
                hero_name = row['Hero'].replace(" ", "_").replace(".", "")
                perk_name = row['Perk Name'].replace(" ", "_").replace(".", "")
                
                # Create a unique filename
                filename = f"{hero_name}_{perk_name}.png"
                
                # Clean filename further - remove any invalid characters
                filename = re.sub(r'[^\w\.-]', '_', filename)
                    
                local_path = os.path.join('perk_icons', filename)
                
                # Check if file already exists
                if filename in existing_perk_icons:
                    print(f"Perk icon already exists: {filename}")
                    local_perk_paths.append(local_path)
                else:
                    # Download the image
                    print(f"Downloading perk icon: {icon_url} as {filename}")
                    img_response = requests.get(icon_url, stream=True)
                    
                    if img_response.status_code == 200:
                        with open(local_path, 'wb') as f:
                            for chunk in img_response.iter_content(1024):
                                f.write(chunk)
                                
                        local_perk_paths.append(local_path)
                        existing_perk_icons.add(filename)  # Add to our tracking set
                        print(f"Downloaded to {local_path}")
                    else:
                        print(f"Failed to download {icon_url}")
                        local_perk_paths.append("")
            except Exception as e:
                print(f"Error downloading perk icon {icon_url}: {e}")
                local_perk_paths.append("")
        
        # Process hero icon (only once per hero)
        hero_name = row['Hero']
        hero_icon_url = row['Hero Icon URL']
        
        if hero_name not in processed_heroes and hero_icon_url:
            try:
                # Create a filename for the hero icon
                hero_filename = f"{hero_name.replace(' ', '_').replace('.', '')}.png"
                hero_filename = re.sub(r'[^\w\.-]', '_', hero_filename)
                
                local_hero_path = os.path.join('hero_icons', hero_filename)
                
                # Check if file already exists
                if hero_filename in existing_hero_icons:
                    print(f"Hero icon already exists: {hero_filename}")
                else:
                    # Download the hero icon
                    print(f"Downloading hero icon: {hero_icon_url} as {hero_filename}")
                    hero_img_response = requests.get(hero_icon_url, stream=True)
                    
                    if hero_img_response.status_code == 200:
                        with open(local_hero_path, 'wb') as f:
                            for chunk in hero_img_response.iter_content(1024):
                                f.write(chunk)
                        
                        print(f"Downloaded hero icon to {local_hero_path}")
                        existing_hero_icons.add(hero_filename)  # Add to our tracking set
                    else:
                        print(f"Failed to download hero icon {hero_icon_url}")
                
                processed_heroes.add(hero_name)
                
            except Exception as e:
                print(f"Error downloading hero icon {hero_icon_url}: {e}")
        
        # Record the path for this row (even if we've seen this hero before)
        if hero_name:
            hero_filename = f"{hero_name.replace(' ', '_').replace('.', '')}.png"
            hero_filename = re.sub(r'[^\w\.-]', '_', hero_filename)
            local_hero_paths.append(os.path.join('hero_icons', hero_filename))
        else:
            local_hero_paths.append("")
    
    # Add local paths to dataframe
    dataframe['Local Icon Path'] = local_perk_paths
    dataframe['Local Hero Icon Path'] = local_hero_paths
    return dataframe

def save_to_formats(dataframe):
    # Save to CSV
    dataframe.to_csv('overwatch_perks.csv', index=False)
    print("Data saved to overwatch_perks.csv")
    
    # Save to Excel
    dataframe.to_excel('overwatch_perks.xlsx', index=False)
    print("Data saved to overwatch_perks.xlsx")
    
    # Save to HTML with flashcard functionality
    html_output = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Overwatch 2 Perks</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Exo+2:ital,wght@0,100..900;1,100..900&display=swap" rel="stylesheet">
        <style>
            @font-face {
                font-family: 'Overwatch' ;
                src: url('Overwatch_Oblique.ttf') format('truetype');
            }
            * {
                -ms-overflow-style: none;  /* IE and Edge */
                scrollbar-width: none;  /* Firefox */
            }
            *::-webkit-scrollbar {
                display: none;
            }
            body {
                background-color: #1e1f23;
                font-family: "Exo 2", sans-serif;
                margin: 20px;
            }
            h1 {
                font-family: 'Overwatch';
                font-weight: 400;
                font-size: 3em;
                color: #ffffff;
                text-align: center;
            }
            .controls {
                margin: 20px 0;
                text-align: center;
            }
            .filters {
                margin: 5px 0;
                display: flex;
                justify-content: center;
                gap: 5px;
                flex-wrap: wrap;
            }
            .flashcard-container {
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
                justify-content: center;
            }
            .flashcard {
                width: 300px;
                height: 300px;
                perspective: 1000px;
            }
            .flashcard-front:hover {
                background-color: #353841;
                cursor: pointer;
            }
            .flashcard-inner {
                position: relative;
                width: 100%;
                height: 100%;
                text-align: center;
                transition: transform 0.6s;
                transform-style: preserve-3d;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                border-radius: 10px;
            }
            .flashcard.flipped .flashcard-inner {
                transform: rotateY(180deg);
            }
            .flashcard-front, .flashcard-back {
                position: absolute;
                width: 100%;
                height: 100%;
                -webkit-backface-visibility: hidden;
                backface-visibility: hidden;
                border-radius: 10px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                padding: 20px;
                box-sizing: border-box;
            }
            .flashcard-front {
                background-color: #27292f;
                color: white;
            }
            .flashcard-back {
                background-color: #353841;
                color: #333;
                transform: rotateY(180deg);
            }
            .flashcard-back:hover {
                cursor: pointer;
            }
            .perk-icon {
                width: 50px;
                height: 50px;
                border-radius: 100px;
                outline: 1px solid #42474d;
                outline-offset: 15px;
                object-fit: contain;
                margin-top: 40px;
            }
            .hero-name {
                font-family: "Overwatch";
                font-size: 2em;
                font-weight: 400;
                color: white;
            }
            .perk-name {
                font-family: "Overwatch";
                color: white;
                font-size: 1.6em;
                font-weight: 200;
                margin: 10px 0 0 0;
            }
            .perk-tier {
                font-size: 0.8em;
                font-weight: 400;
                text-transform: uppercase;
                margin-bottom: 15px;
                color: #f06414;
            }
            .perk-tier.major {
                color: #f06414;
            }
            .perk-tier.minor {
                color: #76ABFF;
            }
            .perk-description {
                color: #eeeeee;
                font-size: 0.8em;
            }
            button {
                font-family: 'Overwatch';
                font-size: 1.4em;
                font-weight: 500;
                background-color: #f06414;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                margin: 0 1px;
                cursor: pointer;
            }
            button:hover {
                background-color: #E88A0C;
            }
            select {
                font-family: 'Overwatch';
                font-size: 1.1em;
                font-weight: 100;
                padding: 6px;
                border-radius: 5px;
                border: none;
            }
            .stats {
                text-align: center;
                margin: 20px 0;
                font-size: 0.7em;
                color: #777;
            }
            @media (max-width: 768px) {
                .filters {
                    flex-direction: column;
                    align-items: center;
                }
                select {
                    width: 80%;
                }
            }
        </style>
    </head>
    <body>
        <h1>Overwatch 2 Perks</h1>
        
        <div class="controls">
            <button id="flip-all">Flip All Cards</button>
            <button id="reset">Reset Cards</button>
            <button id="shuffle">Shuffle Cards</button>
        </div>
        
        <div class="filters">
            <select id="role-filter">
                <option value="all">All Roles</option>
                <option value="Tanks">Tanks</option>
                <option value="Damage">Damage</option>
                <option value="Support">Support</option>
            </select>
            
            <select id="hero-filter">
                <option value="all">All Heroes</option>
            </select>
            
            <select id="tier-filter">
                <option value="all">All Tiers</option>
                <option value="Major Perk">Major Perks</option>
                <option value="Minor Perk">Minor Perks</option>
            </select>
        </div>
        
        <div class="stats" id="stats"></div>
        
        <div class="flashcard-container" id="flashcards">
    """
    
    # Generate flashcard HTML for each perk
    for i, (_, row) in enumerate(dataframe.iterrows()):
        hero_icon_path = f"hero_icons/{row['Hero'].replace(' ', '_').replace('.', '').replace(':', '_')}.png"
        tier_class = "major" if "Major" in row['Tier'] else "minor"
        
        # Use local path if available, otherwise use URL
        icon_path = row['Local Icon Path'] if row['Local Icon Path'] else row['Icon URL']
        
        html_output += f"""
        <div class="flashcard" data-role="{row['Role']}" data-hero="{row['Hero']}" data-tier="{row['Tier']}">
            <div class="flashcard-inner">
                <div class="flashcard-front">
                    <img src="{icon_path}" alt="{row['Perk Name']} icon" class="perk-icon" onerror="this.src='https://static.wikia.nocookie.net/overwatch_gamepedia/images/b/bd/Icon-Overwatch_2.png/revision/latest/scale-to-width-down/50';">
                </div>
                <div class="flashcard-back">

                    <img src="{hero_icon_path}" class="hero-icon" alt="Hero Icon">
                    <div class="perk-name">{row['Perk Name']}</div>
                    <div class="perk-tier {tier_class}">{row['Tier']}</div>
                    <p class="perk-description">{row['Description']}</p>
                </div>
            </div>
        </div>
        """
    
    # Add JavaScript for interactivity
    html_output += """
        </div>
        
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                // Get all card elements
                const cards = document.querySelectorAll('.flashcard');
                
                // Store the original order of cards
                const originalOrder = Array.from(cards);
                
                // Function to attach click handlers to cards
                function attachCardClickHandlers() {
                    document.querySelectorAll('.flashcard').forEach(card => {
                        // Remove existing listener first to prevent duplicates
                        card.removeEventListener('click', flipCard);
                        // Add the click handler
                        card.addEventListener('click', flipCard);
                    });
                }
                
                // Card flip function
                function flipCard() {
                    this.classList.toggle('flipped');
                }
                
                // Initial attachment of click handlers
                attachCardClickHandlers();
                
                // Convert selects to multi-select toggle buttons
                function convertSelectsToToggleButtons() {
                    const filtersContainer = document.createElement('div');
                    filtersContainer.className = 'filters-container';
                    filtersContainer.style.display = 'flex';
                    filtersContainer.style.flexDirection = 'column';
                    filtersContainer.style.alignItems = 'center';
                    filtersContainer.style.gap = '5px';
                    filtersContainer.style.margin = '10px 0 20px 0';
                    
                    // Group heroes by role
                    const heroesByRole = {
                        'Tanks': [],
                        'Damage': [],
                        'Support': []
                    };
                    
                    // Process heroes and store them with their roles
                    const processedHeroes = new Set();
                    Array.from(cards).forEach(card => {
                        const hero = card.dataset.hero;
                        const role = card.dataset.role;
                        
                        if (!processedHeroes.has(hero) && role in heroesByRole) {
                            const heroIconPath = `hero_icons/${hero.replace(' ', '_').replace('.', '').replace(':', '_')}.png`;
                            heroesByRole[role].push({ name: hero, iconPath: heroIconPath });
                            processedHeroes.add(hero);
                        }
                    });
                    
                    // Sort heroes in each role alphabetically
                    Object.keys(heroesByRole).forEach(role => {
                        heroesByRole[role].sort((a, b) => a.name.localeCompare(b.name));
                    });
                    
                    // Create hero filters by role
                    const roleOrder = ['Tanks', 'Damage', 'Support'];
                    roleOrder.forEach(role => {
                        // Create row for this role's heroes
                        const heroRowContainer = document.createElement('div');
                        heroRowContainer.className = `hero-toggle-group toggle-group ${role.toLowerCase()}-heroes`;
                        heroRowContainer.style.display = 'flex';
                        heroRowContainer.style.flexWrap = 'wrap';
                        heroRowContainer.style.gap = '5px';
                        heroRowContainer.style.justifyContent = 'center';
                        heroRowContainer.style.margin = '5px 0';
                        heroRowContainer.style.maxWidth = '80%';
                        
                        // Create hero icons for this role
                        heroesByRole[role].forEach(hero => {
                            const iconButton = document.createElement('div');
                            iconButton.className = 'hero-filter-icon';
                            iconButton.dataset.value = hero.name;
                            iconButton.dataset.filterType = 'hero';
                            iconButton.dataset.role = role;
                            iconButton.title = hero.name;
                            
                            // Style the button as a circular icon
                            iconButton.style.width = '50px';
                            iconButton.style.height = '50px';
                            iconButton.style.borderRadius = '50%';
                            iconButton.style.overflow = 'hidden';
                            iconButton.style.cursor = 'pointer';
                            iconButton.style.border = '2px solid #4D4D4D';
                            iconButton.style.padding = '2px';
                            iconButton.style.backgroundColor = '#27292f';
                            iconButton.style.transition = 'all 0.2s ease';
                            
                            // Create the image element
                            const img = document.createElement('img');
                            img.src = hero.iconPath;
                            img.alt = hero.name;
                            img.style.width = '100%';
                            img.style.height = '100%';
                            img.style.objectFit = 'cover';
                            img.style.borderRadius = '50%';
                            
                            // Add fallback for image load errors
                            img.onerror = function() {
                                this.src = 'https://static.wikia.nocookie.net/overwatch_gamepedia/images/b/bd/Icon-Overwatch_2.png/revision/latest/scale-to-width-down/50';
                            };
                            
                            iconButton.appendChild(img);
                            
                            // Click handler for toggle buttons
                            iconButton.addEventListener('click', function() {
                                this.classList.toggle('active');
                                
                                if (this.classList.contains('active')) {
                                    this.style.border = '2px solid #f06414';
                                    this.style.boxShadow = '0 0 10px #f06414';
                                } else {
                                    this.style.border = '2px solid #4D4D4D';
                                    this.style.boxShadow = 'none';
                                }
                                
                                applyFilters();
                            });
                            
                            heroRowContainer.appendChild(iconButton);
                        });
                        
                        // Add this role's heroes to container
                        filtersContainer.appendChild(heroRowContainer);
                    });
                    
                    // Regular role and tier filters
                    const filters = ['role', 'tier'];
                    filters.forEach(filterType => {
                        const selectElement = document.getElementById(`${filterType}-filter`);
                        const options = Array.from(selectElement.options);
                        
                        // Create a new container for buttons
                        const buttonContainer = document.createElement('div');
                        buttonContainer.className = `${filterType}-toggle-group toggle-group`;
                        buttonContainer.style.display = 'flex';
                        buttonContainer.style.flexWrap = 'wrap';
                        buttonContainer.style.gap = '5px';
                        buttonContainer.style.justifyContent = 'center';
                        
                        // Create toggle buttons for each option (skipping "all")
                        options.forEach(option => {
                            if (option.value === 'all') return; // Skip the "all" option
                            
                            const button = document.createElement('button');
                            button.textContent = option.textContent;
                            button.dataset.value = option.value;
                            button.dataset.filterType = filterType;
                            button.className = 'filter-toggle';
                            button.style.backgroundColor = '#4D4D4D';
                            button.style.opacity = '0.6';
                            button.style.margin = '3px';

                            // Click handler for toggle buttons
                            button.addEventListener('click', function() {
                                this.classList.toggle('active');
                                
                                if (this.classList.contains('active')) {
                                    this.style.backgroundColor = '#f06414';
                                    this.style.opacity = '1';
                                } else {
                                    this.style.backgroundColor = '#4D4D4D';
                                    this.style.opacity = '0.6';
                                }
                                
                                applyFilters();
                            });
                            
                            buttonContainer.appendChild(button);
                        });
                        
                        // Add to filters container
                        filtersContainer.appendChild(buttonContainer);
                    });
                    
                    // Replace the old filters div with our new container
                    const oldFiltersDiv = document.querySelector('.filters');
                    oldFiltersDiv.parentNode.replaceChild(filtersContainer, oldFiltersDiv);
                }
                
                // Call the function to convert selects to toggle buttons
                convertSelectsToToggleButtons();
                
                // Modify the front of cards to show hero name
                cards.forEach(card => {
                    const heroName = card.dataset.hero;
                    const frontSide = card.querySelector('.flashcard-front');
                    
                    // Create hero name element
                    const heroNameElement = document.createElement('div');
                    heroNameElement.className = 'hero-name-front';
                    heroNameElement.textContent = heroName;
                    heroNameElement.style.marginTop = '30px';
                    heroNameElement.style.fontFamily = "'Overwatch'";
                    heroNameElement.style.fontSize = '1.4em';
                    heroNameElement.style.color = 'white';
                    
                    // Add it to the front side
                    frontSide.appendChild(heroNameElement);
                });
                
                // Updated applyFilters function for toggle buttons
                function applyFilters() {
                    // Get active filters
                    const activeRoles = Array.from(document.querySelectorAll('.role-toggle-group .filter-toggle.active'))
                        .map(btn => btn.dataset.value);
                    
                    const activeHeroes = Array.from(document.querySelectorAll('.hero-toggle-group .hero-filter-icon.active'))
                        .map(btn => btn.dataset.value);
                    
                    const activeTiers = Array.from(document.querySelectorAll('.tier-toggle-group .filter-toggle.active'))
                        .map(btn => btn.dataset.value);
                    
                    let visibleCount = 0;
                    
                    cards.forEach(card => {
                        const cardRole = card.dataset.role;
                        const cardHero = card.dataset.hero;
                        const cardTier = card.dataset.tier;
                        
                        const matchesRole = activeRoles.length === 0 || activeRoles.includes(cardRole);
                        const matchesHero = activeHeroes.length === 0 || activeHeroes.includes(cardHero);
                        const matchesTier = activeTiers.length === 0 || activeTiers.includes(cardTier);
                        
                        if (matchesRole && matchesHero && matchesTier) {
                            card.style.display = 'block';
                            visibleCount++;
                        } else {
                            card.style.display = 'none';
                        }
                    });
                    
                    // Update stats
                    document.getElementById('stats').textContent = `SHOWING ${visibleCount} OF ${cards.length} PERKS`;
                }
                
                // Reset all cards button - now also resets filters
                document.getElementById('reset').addEventListener('click', function() {
                    const container = document.getElementById('flashcards');
                    
                    // Remove flipped class from all cards
                    cards.forEach(card => {
                        card.classList.remove('flipped');
                    });
                    
                    // Reset regular toggle filters
                    document.querySelectorAll('.filter-toggle.active').forEach(button => {
                        button.classList.remove('active');
                        button.style.backgroundColor = '#4D4D4D';
                        button.style.opacity = '0.6';
                    });
                    
                    // Reset hero icon filters
                    document.querySelectorAll('.hero-filter-icon.active').forEach(icon => {
                        icon.classList.remove('active');
                        icon.style.border = '2px solid #4D4D4D';
                        icon.style.boxShadow = 'none';
                    });
                    
                    // Restore original order
                    originalOrder.forEach(card => {
                        container.appendChild(card);
                    });
                    
                    // Reattach click handlers
                    attachCardClickHandlers();
                    
                    // Apply filters (with all filters inactive, this will show all cards)
                    applyFilters();
                });
                
                // Update your shuffle button too
                document.getElementById('shuffle').addEventListener('click', function() {
                    const container = document.getElementById('flashcards');
                    const cardsArray = Array.from(cards).filter(card => card.style.display !== 'none');
                    
                    for (let i = cardsArray.length - 1; i > 0; i--) {
                        const j = Math.floor(Math.random() * (i + 1));
                        [cardsArray[i], cardsArray[j]] = [cardsArray[j], cardsArray[i]];
                    }
                    
                    cardsArray.forEach(card => {
                        container.appendChild(card);
                    });
                    
                    // Reattach click handlers after shuffling
                    attachCardClickHandlers();
                });
                
                // Initial filter application
                applyFilters();
            });
        </script>
    </body>
    </html>
    """
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_output)
    print("Data saved to index.html")

if __name__ == "__main__":
    print("Scraping Overwatch perks data...")
    perks_data = scrape_overwatch_perks()
    
    if perks_data is not None and not perks_data.empty:
        print(f"Successfully scraped {len(perks_data)} perks!")
        
        # Download images
        print("Downloading perk icons...")
        perks_data = download_images(perks_data)
        
        save_to_formats(perks_data)
    else:
        print("Failed to scrape perks data.")