# GitLabRepoSync

GitLabRepoSync is a tool for synchronizing local Git repositories with their remote within a group.

## Features

- Synchronize local repositories with GitLab
- Automatically clone new repositories
- Delete local repositories that do not exist on GitLab
- Support for additional directories to delete
- Update existing repositories to the latest state from the remote

## Installation

Install dependencies:

```
pip install -r requirements.txt
```

## Usage

### Basic Usage

```
python gitlab_repo_sync.py --group_id your-group-id --base_directory /path/to/base
```

### Full Example with All Options

```
python gitlab_repo_sync.py \
    --group_id group \
    --base_directory /Users/user.user/repository \
    --group_directory /Users/user.user/repository/kitopi-com \
    --include_directories dir1 dir2 \
    --force \
    --dry_run \
    --update
```

### Parameters

- `--group_id`: GitLab group ID or full path.
- `--base_directory`: Base directory for locating repositories (default: current working directory).
- `--group_directory`: Path to the GitLab group directory (if different from base_directory/group_id).
- `--include_directories`: Additional folders to delete (space-separated paths).
- `--force`: Delete directories without user confirmation.
- `--dry_run`: Simulate delete operations without actually performing them.
- `--update`: Update all Git repositories in the --base_directory to their latest state from the remote.
