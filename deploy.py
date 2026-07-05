import os
import subprocess
import sys
import glob

def find_git():
    """Locate the git executable, checking PATH, standard installs, and GitHub Desktop."""
    # 1. Try standard system git command
    try:
        # Run a simple git command to see if it is in PATH
        result = subprocess.run(["git", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return "git"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # 2. Check standard Windows installations
    pf_git = r"C:\Program Files\Git\cmd\git.exe"
    if os.path.exists(pf_git):
        return pf_git

    pf_x86_git = r"C:\Program Files (x86)\Git\cmd\git.exe"
    if os.path.exists(pf_x86_git):
        return pf_x86_git

    # 3. Check GitHub Desktop location (Windows user directory)
    user_profile = os.environ.get("USERPROFILE", "")
    if user_profile:
        # Locate git.exe inside the GitHub Desktop resources directory
        gh_desktop_git_pattern = os.path.join(user_profile, "AppData", "Local", "GitHubDesktop", "app-*", "resources", "app", "git", "cmd", "git.exe")
        matches = glob.glob(gh_desktop_git_pattern)
        if matches:
            # Sort to get the latest app version directory
            matches.sort(reverse=True)
            return matches[0]

    return None

def run_git(git_bin, args):
    """Runs a git command with specified arguments."""
    cmd = [git_bin] + args
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0

def main():
    git_bin = find_git()
    if not git_bin:
        print("ERROR: Git executable could not be found on this system.")
        print("Please make sure Git or GitHub Desktop is installed.")
        sys.exit(1)
        
    print(f"Using Git: {git_bin}\n")
    
    # Check if there are changes to commit
    # We run status --porcelain to see if anything is modified/untracked
    status_result = subprocess.run([git_bin, "status", "--porcelain"], capture_output=True, text=True)
    if not status_result.stdout.strip():
        print("Everything is up-to-date. No changes detected to deploy.")
        sys.exit(0)
        
    # Get commit message
    commit_msg = "Update code"
    if len(sys.argv) > 1:
        commit_msg = " ".join(sys.argv[1:])
        
    print("Changes detected. Preparing to deploy to Live Project...")
    
    # 1. Git add
    if not run_git(git_bin, ["add", "."]):
        print("ERROR: Failed to stage changes.")
        sys.exit(1)
        
    # 2. Git commit
    if not run_git(git_bin, ["commit", "-m", commit_msg]):
        print("ERROR: Failed to commit changes.")
        sys.exit(1)
        
    # 3. Git push
    print("\nPushing changes to GitHub (Render will auto-deploy once pushed)...")
    if not run_git(git_bin, ["push", "origin", "main"]):
        print("ERROR: Failed to push changes to origin main.")
        print("Make sure you are authenticated with GitHub (e.g., via GitHub Desktop or credential manager).")
        sys.exit(1)
        
    print("\nSUCCESS: Changes successfully pushed to GitHub!")
    print("Render has been notified and is automatically building and deploying your live project.")
    print("You can monitor the deploy status on your Render dashboard.")

if __name__ == "__main__":
    main()
