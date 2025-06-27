import os

def list_all_files(directory):
    try:
        for root, dirs, files in os.walk(directory):
            # Convert root to relative path from the base directory
            rel_root = os.path.relpath(root, directory)
            if rel_root == ".":
                rel_root = ""
            
            # Exclude venv and __pycache__ folders
            dirs[:] = [d for d in dirs if d not in ["venv", "__pycache__", ".git"]]
            
            # Print directories
            for dir_name in dirs:
                full_path = os.path.join(rel_root, dir_name)
                basename = dir_name
                print(f"{full_path} {basename}")
            
            # Print files
            for file_name in files:
                full_path = os.path.join(rel_root, file_name)
                basename = file_name
                print(f"{full_path} {basename}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    directory_path = "C:\\Users\\akhee\\Documents\\GitHub\\lms-project"
    if not os.path.isdir(directory_path):
        print("Invalid directory path!")
    else:
        list_all_files(directory_path)