import sqlite3

DATABASE = 'recipes.db'


def get_db_connection():  # database connection logic into a function
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # rows behave like dictionaries
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()  # ursor to execute SQL queries and fetch results

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            hash TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL DEFAULT ''
        )
    ''')

    # Insert a special 'system_recipes' user
    # system_recipes user will own the default recipes. No hash as it won't log in
    try:
        cursor.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                       ('system_recipes', 'NO_LOGIN_HASH'))
        conn.commit()
        print("System recipes user created (if not already exists).")
    except sqlite3.IntegrityError:
        # system_recipes user already exists
        pass

    # Retrieve the ID of the system_recipes user
    cursor.execute("SELECT id FROM users WHERE username = 'system_recipes'")
    # put it into a variable for easy access
    system_user_id = cursor.fetchone()['id']

    # Create recipes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            instructions TEXT NOT NULL,
            prep_time TEXT,
            cook_time TEXT,
            image_filename TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recipes_user_id ON recipes(user_id)")


    # Create ingredients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            quantity_unit TEXT,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ingredients_recipe_id ON ingredients(recipe_id)")

    # Create categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    # Create recipe_categories junction table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recipe_categories (
            recipe_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            PRIMARY KEY (recipe_id, category_id),
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recipe_categories_category_id ON recipe_categories(category_id)")


    # Password reset tokens
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL, -- Stored as ISO 8601 string (YYYY-MM-DD HH:MM:SS)
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Favorites table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL,
            recipe_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, recipe_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id)")


    conn.commit()
    conn.close()
    print("Database tables created successfully!")
    return system_user_id


def populate_default_data(system_user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- Add Default Categories --- into categories table
    default_categories = ["Breakfast", "Lunch", "Dinner", "Dessert", "Appetizer", "Main Course",
                          "Side Dish", "Snack", "Italian", "Mexican", "Asian", "Vegetarian", "Vegan", "Quick & Easy", "Seafood", "Baking", "Comfort Food", "Soups", "Salads",
                          "Smoothies", "Grilling", "Mediterranean"]
    category_ids = {}

    for category_name in default_categories:
        try:
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
            category_ids[category_name] = cursor.lastrowid
        except sqlite3.IntegrityError:
            # category already exists, just fetch its ID
            cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
            category_ids[category_name] = cursor.fetchone()["id"]
        conn.commit()
    print("Default categories populated.")

    # --- Add Default Recipes ---
    # list of dictionaries, each represents a default recipe
    default_recipes = [
        # SPAGHETTI BOLOGNESE
        {
            "title": "Classic Spaghetti Bolognese",
            "description": "A rich and hearty Italian meat sauce served with spaghetti.",
            "instructions": "1. Brown ground meat. 2. Add onions, carrots, celery and cook. 3. Stir in crushed tomatoes, herbs, and simmer for at least 1 hour. 4. Serve over cooked spaghetti with parmesan.",
            "prep_time": "20 mins",
            "cook_time": "1 hour 30 mins",
            "image_filename": "spaghetti_bolognese.jpg",
            "ingredients": [
                {"name": "Ground Beef", "quantity_unit": "500g"},
                {"name": "Crushed Tomatoes", "quantity_unit": "800g can"},
                {"name": "Onion", "quantity_unit": "1 large, chopped"},
                {"name": "Garlic", "quantity_unit": "3 cloves, minced"},
                {"name": "Carrot", "quantity_unit": "1, diced"},
                {"name": "Celery Stalk", "quantity_unit": "1, diced"},
                {"name": "Beef Broth", "quantity_unit": "250ml"},
                {"name": "Red Wine", "quantity_unit": "125ml (optional)"},
                {"name": "Spaghetti", "quantity_unit": "400g"},
                {"name": "Parmesan Cheese", "quantity_unit": "for serving"}
            ],
            "categories": ["Main Course", "Italian", "Dinner"]
        },
        # SCRAMBLE EGGS
        {
            "title": "Simple Scrambled Eggs",
            "description": "Fluffy scrambled eggs perfect for breakfast.",
            "instructions": "1. Whisk eggs with a splash of milk/cream, salt, and pepper. 2. Melt butter in a non-stick pan over medium-low heat. 3. Pour in egg mixture. 4. Gently push cooked egg from edges to center until mostly set but still moist. 5. Serve immediately.",
            "prep_time": "2 mins",
            "cook_time": "5 mins",
            "image_filename": "scrambled_eggs.jpg",
            "ingredients": [
                {"name": "Eggs", "quantity_unit": "3 large"},
                {"name": "Milk or Cream", "quantity_unit": "1 tbsp"},
                {"name": "Butter", "quantity_unit": "1 tsp"},
                {"name": "Salt", "quantity_unit": "to taste"},
                {"name": "Black Pepper", "quantity_unit": "to taste"}
            ],
            "categories": ["Breakfast", "Quick & Easy"]
        },
        # CLASSIC GUACAMOLE
        {
            "title": "Classic Guacamole",
            "description": "A fresh and simple dip with ripe avocados, lime, and cilantro.",
            "instructions": "1. Mash avocados in a bowl. 2. Mix in diced onion, chopped cilantro, minced jalapeño, and salt. 3. Squeeze fresh lime juice over the mixture and stir to combine. 4. Serve immediately with tortilla chips.",
            "prep_time": "10 mins",
            "cook_time": None,
            "image_filename": "classic_guacamole.jpg",
            "ingredients": [
                {"name": "Avocados", "quantity_unit": "3 ripe"},
                {"name": "Red Onion", "quantity_unit": "1/4 cup, diced"},
                {"name": "Cilantro", "quantity_unit": "1/4 cup, chopped"},
                {"name": "Jalapeño", "quantity_unit": "1, finely minced (optional)"},
                {"name": "Lime", "quantity_unit": "1, juiced"},
                {"name": "Salt", "quantity_unit": "1/2 tsp"}
            ],
            "categories": ["Appetizer", "Snack", "Mexican", "Quick & Easy"]
        },
        # LEMON HERB ROAST CHICKEN
        {
            "title": "Lemon Herb Roast Chicken",
            "description": "Juicy, tender roasted chicken with bright lemon and savory herbs.",
            "instructions": "1. Pat chicken dry and season generously with salt and pepper. 2. Stuff the cavity with a cut lemon, garlic, and fresh herbs like rosemary and thyme. 3. Rub with olive oil and place in a roasting pan. 4. Roast at 400°F (200°C) for 1 hour 20 minutes, or until the internal temperature reaches 165°F (74°C).",
            "prep_time": "15 mins",
            "cook_time": "1 hr 20 mins",
            "image_filename": "lemon_herb_roast_chicken.jpg",
            "ingredients": [
                {"name": "Whole Chicken", "quantity_unit": "1 (about 1.5kg)"},
                {"name": "Lemon", "quantity_unit": "1, halved"},
                {"name": "Garlic", "quantity_unit": "6 cloves"},
                {"name": "Fresh Rosemary", "quantity_unit": "2 sprigs"},
                {"name": "Fresh Thyme", "quantity_unit": "2 sprigs"},
                {"name": "Olive Oil", "quantity_unit": "2 tbsp"},
                {"name": "Salt and Pepper", "quantity_unit": "to taste"}
            ],
            "categories": ["Main Course", "Dinner", "Comfort Food"]
        },
        # VEGETABLE STIR-FRY
        {
            "title": "Quick Vegetable Stir-Fry",
            "description": "A healthy and customizable stir-fry packed with fresh vegetables.",
            "instructions": "1. Prepare sauce by whisking soy sauce, ginger, and garlic. 2. Heat oil in a wok or large pan. 3. Add hard vegetables like broccoli and carrots first and stir-fry for 3-4 minutes. 4. Add softer vegetables like bell peppers and snap peas and cook until tender-crisp. 5. Pour sauce over vegetables and toss to coat. Serve immediately, optionally over rice.",
            "prep_time": "15 mins",
            "cook_time": "10 mins",
            "image_filename": "vegetable_stir_fry.jpg",
            "ingredients": [
                {"name": "Broccoli Florets", "quantity_unit": "2 cups"},
                {"name": "Carrots", "quantity_unit": "1 cup, sliced"},
                {"name": "Bell Pepper", "quantity_unit": "1, sliced"},
                {"name": "Snap Peas", "quantity_unit": "1 cup"},
                {"name": "Soy Sauce", "quantity_unit": "1/4 cup"},
                {"name": "Ginger", "quantity_unit": "1 tsp, grated"},
                {"name": "Garlic", "quantity_unit": "2 cloves, minced"}
            ],
            "categories": ["Side Dish", "Asian", "Vegetarian", "Vegan", "Quick & Easy"]
        },
        # PESTO PASTA
        {
            "title": "Simple Pesto Pasta",
            "description": "A fresh and delicious pasta dish made with basil pesto.",
            "instructions": "1. Cook pasta according to package directions. 2. While pasta is cooking, toast pine nuts in a dry pan. 3. In a food processor, combine basil, toasted pine nuts, garlic, parmesan, and olive oil. Blend until a smooth paste forms. 4. Drain pasta, reserving a little pasta water. 5. Toss pasta with pesto, adding a little pasta water to reach desired consistency. Serve with extra parmesan.",
            "prep_time": "10 mins",
            "cook_time": "15 mins",
            "image_filename": "pesto_pasta.jpg",
            "ingredients": [
                {"name": "Pasta (e.g., Fusilli or Penne)", "quantity_unit": "400g"},
                {"name": "Fresh Basil", "quantity_unit": "2 cups, packed"},
                {"name": "Pine Nuts", "quantity_unit": "1/2 cup"},
                {"name": "Garlic", "quantity_unit": "2 cloves"},
                {"name": "Parmesan Cheese", "quantity_unit": "1/2 cup, grated"},
                {"name": "Extra Virgin Olive Oil", "quantity_unit": "1/2 cup"}
            ],
            "categories": ["Main Course", "Italian", "Vegetarian", "Quick & Easy"]
        },
        # HOMEMADE PIZZA
        {
            "title": "Homemade Pepperoni Pizza",
            "description": "Classic pepperoni pizza made at home with a crispy crust.",
            "instructions": "1. Preheat oven to 475°F (245°C) with a pizza stone or baking sheet inside. 2. Roll out dough and place on parchment paper. 3. Spread pizza sauce evenly, leaving a 1-inch border. 4. Top with mozzarella and pepperoni slices. 5. Bake for 10-15 minutes, or until the crust is golden brown and cheese is bubbly.",
            "prep_time": "20 mins",
            "cook_time": "15 mins",
            "image_filename": "homemade_pizza.jpg",
            "ingredients": [
                {"name": "Pizza Dough", "quantity_unit": "1 ball"},
                {"name": "Pizza Sauce", "quantity_unit": "1/2 cup"},
                {"name": "Mozzarella Cheese", "quantity_unit": "1.5 cups, shredded"},
                {"name": "Pepperoni Slices", "quantity_unit": "1/2 cup"}
            ],
            "categories": ["Main Course", "Italian", "Dinner", "Comfort Food"]
        },
        # CHICKEN FAJITAS
        {
            "title": "Easy Chicken Fajitas",
            "description": "Sizzling chicken and bell peppers served with warm tortillas.",
            "instructions": "1. Slice chicken breast and bell peppers. 2. In a bowl, toss chicken and peppers with olive oil and fajita seasoning. 3. Heat a large skillet over medium-high heat and cook the mixture, stirring often, until chicken is cooked through and vegetables are tender-crisp. 4. Serve immediately with warm tortillas and your favorite toppings like sour cream and salsa.",
            "prep_time": "15 mins",
            "cook_time": "20 mins",
            "image_filename": "chicken_fajitas.jpg",
            "ingredients": [
                {"name": "Chicken Breast", "quantity_unit": "2, sliced"},
                {"name": "Bell Peppers", "quantity_unit": "2, sliced"},
                {"name": "Onion", "quantity_unit": "1, sliced"},
                {"name": "Fajita Seasoning", "quantity_unit": "2 tbsp"},
                {"name": "Olive Oil", "quantity_unit": "1 tbsp"},
                {"name": "Tortillas", "quantity_unit": "8 large"}
            ],
            "categories": ["Main Course", "Mexican", "Dinner"]
        },
        # CHOCOLATE CHIP COOKIES
        {
            "title": "Classic Chocolate Chip Cookies",
            "description": "Soft and chewy cookies with gooey chocolate chips.",
            "instructions": "1. Cream butter and sugars. 2. Beat in eggs and vanilla. 3. In a separate bowl, whisk flour, baking soda, and salt. 4. Gradually add dry ingredients to wet ingredients. 5. Fold in chocolate chips. 6. Drop spoonfuls onto a baking sheet and bake at 375°F (190°C) for 10-12 minutes.",
            "prep_time": "15 mins",
            "cook_time": "12 mins",
            "image_filename": "chocolate_chip_cookies.jpg",
            "ingredients": [
                {"name": "Butter", "quantity_unit": "1/2 cup, softened"},
                {"name": "Brown Sugar", "quantity_unit": "1/2 cup"},
                {"name": "White Sugar", "quantity_unit": "1/4 cup"},
                {"name": "Egg", "quantity_unit": "1 large"},
                {"name": "Vanilla Extract", "quantity_unit": "1 tsp"},
                {"name": "All-purpose Flour", "quantity_unit": "1.5 cups"},
                {"name": "Baking Soda", "quantity_unit": "1/2 tsp"},
                {"name": "Salt", "quantity_unit": "1/4 tsp"},
                {"name": "Chocolate Chips", "quantity_unit": "1 cup"}
            ],
            "categories": ["Dessert", "Baking", "Comfort Food"]
        },
        # HOMEMADE MAC AND CHEESE
        {
            "title": "Creamy Mac and Cheese",
            "description": "The ultimate comfort food with a rich, cheesy sauce.",
            "instructions": "1. Cook pasta according to package directions. 2. In a saucepan, melt butter. Whisk in flour to create a roux. 3. Gradually whisk in milk until smooth. Cook over medium heat until thickened. 4. Reduce heat to low and stir in shredded cheeses until melted and smooth. 5. Season with salt, pepper, and a pinch of nutmeg. 6. Stir in cooked pasta and serve immediately.",
            "prep_time": "10 mins",
            "cook_time": "20 mins",
            "image_filename": "mac_and_cheese.jpg",
            "ingredients": [
                {"name": "Elbow Macaroni", "quantity_unit": "1 box (450g)"},
                {"name": "Butter", "quantity_unit": "1/4 cup"},
                {"name": "All-purpose Flour", "quantity_unit": "1/4 cup"},
                {"name": "Milk", "quantity_unit": "3 cups"},
                {"name": "Cheddar Cheese", "quantity_unit": "2 cups, shredded"},
                {"name": "Gruyère Cheese", "quantity_unit": "1 cup, shredded (optional)"},
                {"name": "Salt and Pepper", "quantity_unit": "to taste"}
            ],
            "categories": ["Main Course", "Side Dish", "Comfort Food", "Vegetarian"]
        }
    ]

    # Add recipes data into recipe table
    for recipe_data in default_recipes:
        try:
            cursor.execute(
                "INSERT INTO recipes (user_id, title, description, instructions, prep_time, cook_time, image_filename) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (system_user_id, recipe_data["title"], recipe_data["description"],
                 recipe_data["instructions"], recipe_data["prep_time"], recipe_data["cook_time"], recipe_data["image_filename"])
            )
            recipe_id = cursor.lastrowid

            # Add default ingredients for the default recipe into table
            for ingredient in recipe_data["ingredients"]:
                cursor.execute(
                    "INSERT INTO ingredients (recipe_id, name, quantity_unit) VALUES (?, ?, ?)",
                    (recipe_id, ingredient["name"], ingredient["quantity_unit"])
                )

            # Link categories to the recipe and Add recipe_id and category_id to recipe_categories Junction table
            for category_name in recipe_data["categories"]:
                if category_name in category_ids:
                    cursor.execute(
                        "INSERT INTO recipe_categories (recipe_id, category_id) VALUES (?, ?)",
                        (recipe_id, category_ids[category_name])
                    )
                else:
                    print(
                        f"Warning: Category '{category_name}' not found for recipe '{recipe_data['title']}'.")

        except sqlite3.IntegrityError as e:
            print(f"Skipping duplicate default recipe: {recipe_data['title']} (Error: {e})")
            # This ensures i don't try to insert the same default recipe multiple times
            pass

    conn.commit()
    conn.close()
    print("Default recipe populated")


if __name__ == '__main__':
    # First create tables and get the system_user_id
    sys_user_id = create_tables()
    # Then populate default data using that ID
    if sys_user_id:
        populate_default_data(sys_user_id)
    else:
        print("Could not retrieve system user ID, skipping default data population.")
