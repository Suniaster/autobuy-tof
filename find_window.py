import pygetwindow as gw

def list_windows():
    print("Listing all visible windows:")
    windows = gw.getAllTitles()
    found = False
    for title in windows:
        if title.strip():
            print(f"- {title}")
            if "Tower" in title or "Fantasy" in title:
                found = True
                print(f"  *** POTENTIAL MATCH FOUND: '{title}' ***")
    
    if not found:
        print("\nCould not find a window clearly named 'Tower of Fantasy'.")
        print("Please verify the game is running.")

if __name__ == "__main__":
    list_windows()
