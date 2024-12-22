import argparse
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests
from requests import Session


class GitLabAPIError(Exception):
    pass


class GitLabRepoCleaner:
    def __init__(
        self,
        group_id: str,
        base_directory: Path,
        group_directory: Optional[Path] = None,
        include_directories: Optional[List[Path]] = None,
        force: bool = False,
        dry_run: bool = False,
    ):
        self.group_id = group_id
        self.base_directory = base_directory.resolve()
        self.group_directory = (
            group_directory.resolve() if group_directory else self.base_directory / self.group_id
        )
        self.include_directories = [
            d.resolve() if d.is_absolute() else (self.base_directory / d).resolve()
            for d in (include_directories or [])
        ]
        self.force = force
        self.dry_run = dry_run
        self.private_token = self.get_private_token()
        self.headers = {"PRIVATE-TOKEN": self.private_token}
        self.session = self._init_session()
        self._check_dependencies()

    @staticmethod
    def setup_logging() -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler()],
        )

    @staticmethod
    def parse_arguments() -> argparse.Namespace:
        parser = argparse.ArgumentParser(
            description="Cleans local Git repositories by synchronizing with GitLab."
        )
        parser.add_argument(
            "--group_id",
            type=str,
            default="",
            help="GitLab group ID or full path (default: kitopi-com)",
        )
        parser.add_argument(
            "--base_directory",
            type=Path,
            default=Path.cwd(),
            help="Base directory for locating repositories (default: current working directory)",
        )
        parser.add_argument(
            "--group_directory",
            type=Path,
            default=None,
            help="Path to the GitLab group directory (if \
                different from base_directory/group_id)",
        )
        parser.add_argument(
            "--include_directories",
            type=Path,
            nargs="*",
            default=[],
            help="Additional folders to delete (relative or absolute paths)",
        )
        parser.add_argument(
            "--force", action="store_true", help="Delete directories without user confirmation"
        )
        parser.add_argument(
            "--dry_run",
            action="store_true",
            help="Simulate delete operations without actually performing them",
        )
        return parser.parse_args()

    @staticmethod
    def get_private_token() -> str:
        token = os.environ.get("GITLAB_TOKEN")
        if not token:
            logging.error("GITLAB_TOKEN is not set in environment variables.")
            raise EnvironmentError("GITLAB_TOKEN is not set in environment variables.")
        return token

    def _init_session(self) -> Session:
        session = requests.Session()
        session.headers.update(self.headers)
        return session

    def _check_dependencies(self) -> None:
        if not shutil.which("glab"):
            logging.error("The 'glab' tool is not installed or not in PATH.")
            raise EnvironmentError("The 'glab' tool is not installed or not in PATH.")

    def run_command(self, cmd: List[str], cwd: Optional[Path] = None) -> None:
        cwd = cwd.resolve() if cwd else None
        try:
            subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None)
            logging.info(f"Executed command: {' '.join(cmd)}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error while executing command {' '.join(cmd)}: {e}")
            raise

    def get_json_response(self, url: str, params: Optional[Dict[str, str]] = None) -> List[Dict]:
        results = []
        page = 1
        while True:
            current_params = params.copy() if params else {}
            current_params.update({"page": page, "per_page": 100})
            response = self.session.get(url, params=current_params)
            if response.status_code == 200:
                try:
                    data = response.json()
                    if not isinstance(data, list):
                        logging.error(f"Expected a list, received: {type(data)}")
                        raise GitLabAPIError(f"Expected a list, received: {type(data)}")
                except ValueError:
                    logging.error(f"Cannot decode JSON response from {url}")
                    raise GitLabAPIError(f"Cannot decode JSON response from {url}")

                if not data:
                    break
                results.extend(data)
                page += 1
            else:
                logging.error(f"Error {response.status_code} while accessing {url}")
                raise GitLabAPIError(f"Error {response.status_code} while accessing {url}")
        return results

    def get_group_repositories(self) -> Dict[str, str]:
        url = f"https://gitlab.com/api/v4/groups/{self.group_id}/projects"
        try:
            projects = self.get_json_response(url, params={"include_subgroups": True})
            return {
                project["path_with_namespace"]: project["http_url_to_repo"]
                for project in projects
            }
        except GitLabAPIError as e:
            logging.error(f"Failed to fetch group repositories: {e}")
            return {}

    def find_local_git_repos(self) -> Dict[str, Path]:
        git_repos = {}
        search_dirs = [self.group_directory]
        for search_dir in search_dirs:
            if not search_dir.is_dir():
                logging.warning(f"Search directory does not exist: {search_dir}")
                continue
            for root, dirs, files in os.walk(search_dir):
                root_path = Path(root)
                if (root_path / ".git").is_dir():
                    repo_path = root_path.resolve()
                    relative_path = repo_path.relative_to(self.base_directory)
                    git_repos[str(relative_path)] = repo_path
                    dirs[:] = [d for d in dirs if d != ".git"]
        return git_repos

    def delete_directories(self, directories: List[Path], description: str) -> None:
        if not directories:
            logging.info(f"No {description} to delete.")
            return

        logging.info(f"\nThe following {description} will be deleted:")
        for directory in directories:
            logging.info(directory)

        if self.force:
            confirm = "yes"
        else:
            confirm = (
                input(f"Do you want to delete these {description}? Type 'yes' to confirm: ")
                .strip()
                .lower()
            )

        if confirm == "yes":
            for directory in directories:
                if self.dry_run:
                    logging.info(f"[Dry Run] Deleted: {directory}")
                    continue
                try:
                    shutil.rmtree(directory)
                    logging.info(f"Deleted: {directory}")
                except Exception as e:
                    logging.error(f"Failed to delete {directory}: {e}")
            if self.dry_run:
                logging.info(f"[Dry Run] Selected {description} have been (simulated) deleted.")
            else:
                logging.info(f"Selected {description} have been deleted.")
        else:
            logging.info(f"No {description} were deleted.")

    def get_user_directories(self) -> List[Path]:
        url = f"https://gitlab.com/api/v4/groups/{self.group_id}/members"
        try:
            users = self.get_json_response(url)
            logging.info(f"Found {len(users)} users in the group.")
        except GitLabAPIError as e:
            logging.error(f"Failed to fetch group members: {e}")
            return []

        user_directories = []
        for user in users:
            username = user.get("username")
            if not username:
                continue
            user_dir = self.base_directory / username
            if user_dir.is_dir():
                user_directories.append(user_dir)
        return user_directories

    def clone_group_repositories(self) -> None:
        logging.info("Cloning group repositories from GitLab...")
        cmd_clone_group = ["glab", "repo", "clone", "-g", self.group_id, "-p", "--paginate"]
        try:
            if not self.dry_run:
                self.run_command(cmd_clone_group, cwd=self.base_directory)
            else:
                logging.info(f"[Dry Run] Executed command: {' '.join(cmd_clone_group)}")
        except subprocess.CalledProcessError:
            logging.error("Failed to clone group repositories.")

    def fetch_gitlab_repositories(self) -> Dict[str, str]:
        gitlab_repositories = self.get_group_repositories()
        logging.info(
            f"Found {len(gitlab_repositories)} repositories in \
                the group and subgroups on GitLab."
        )
        return gitlab_repositories

    def map_gitlab_repos_to_absolute_paths(
        self, gitlab_repositories: Dict[str, str]
    ) -> Set[Path]:
        return {
            (self.base_directory / Path(path)).resolve() for path in gitlab_repositories.keys()
        }

    def identify_repos_to_delete(
        self, local_git_repos: Dict[str, Path], gitlab_repo_absolute_paths: Set[Path]
    ) -> List[Path]:
        repos_to_delete = [
            full_path
            for relative_path, full_path in local_git_repos.items()
            if full_path not in gitlab_repo_absolute_paths
        ]
        for repo in repos_to_delete:
            logging.info(f"Repository to delete: {repo} (not found on GitLab)")
        return repos_to_delete

    def clean_repositories(self) -> None:
        self.clone_group_repositories()
        gitlab_repositories = self.fetch_gitlab_repositories()
        local_git_repos = self.find_local_git_repos()
        logging.info(
            f"Found {len(local_git_repos)} local Git repositories in the group directory."
        )
        gitlab_repo_absolute_paths = self.map_gitlab_repos_to_absolute_paths(gitlab_repositories)
        logging.info("\nGitLab repositories (absolute paths):")
        for repo in gitlab_repo_absolute_paths:
            logging.info(repo)
        logging.info("\nLocal repositories:")
        for repo in local_git_repos.keys():
            logging.info(repo)
        repos_to_delete = self.identify_repos_to_delete(
            local_git_repos, gitlab_repo_absolute_paths
        )
        self.delete_directories(repos_to_delete, "repositories")
        user_directories = self.get_user_directories()
        logging.info(f"Found {len(user_directories)} user directories to delete.")
        self.delete_directories(user_directories, "user directories")
        if self.include_directories:
            logging.info(
                f"Including additional directories for deletion: {self.include_directories}"
            )
            self.delete_directories(self.include_directories, "additional directories")


def main() -> None:
    args = GitLabRepoCleaner.parse_arguments()
    GitLabRepoCleaner.setup_logging()
    cleaner = GitLabRepoCleaner(
        group_id=args.group_id,
        base_directory=args.base_directory,
        group_directory=args.group_directory,
        include_directories=args.include_directories,
        force=args.force,
        dry_run=args.dry_run,
    )
    logging.info(f"Base directory: {cleaner.base_directory}")
    logging.info(f"Group directory: {cleaner.group_directory}")
    logging.info(f"Force delete: {'Enabled' if cleaner.force else 'Disabled'}")
    logging.info(f"Dry run: {'Enabled' if cleaner.dry_run else 'Disabled'}")
    try:
        cleaner.clean_repositories()
    except Exception as e:
        logging.error(f"Repository cleaning process failed: {e}")


if __name__ == "__main__":
    main()
