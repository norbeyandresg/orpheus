import os
import subprocess
import tempfile
import yaml
from dotenv import load_dotenv
from yt_dlp import postprocessor
import eyed3
from typing import Tuple, List, Dict

# load environment variables
load_dotenv()


class AddTrackMetadataPP(postprocessor.PostProcessor):
    def run(self, information: Dict) -> Tuple[List, Dict]:
        # set library path
        self.library_path = os.environ.get("LIBRARY_PATH", "./downloads")
        self.to_screen("Injecting metadata")

        audiofile = eyed3.load(f"{self.library_path}/{information.get('id')}.mp3")

        # ensure audio file is loaded
        assert audiofile, "no audio file loaded"

        if audiofile.tag is None:
            audiofile.initTag()

        # ensure audio file have tag
        assert audiofile.tag, "audio file have no tag info"

        # Add basic tags
        audiofile.tag.title = information.get("title")
        audiofile.tag.album = information.get("album")
        audiofile.tag.artist = information.get("artists", [""])[0]

        audiofile.tag.save()

        return [], information


class BeetsPostProcessor(postprocessor.PostProcessor):
    def run(self, information: Dict) -> Tuple[List, Dict]:
        self.library_path = os.environ.get("LIBRARY_PATH", "./downloads")
        track_path = os.path.join(self.library_path, f"{information.get('id')}.mp3")

        if not os.path.exists(track_path):
            self.to_screen(f"Track file not found: {track_path}")
            return [], information

        self.to_screen(f"Running beets post-processor for: {track_path}")

        # Define beets config
        beets_config = {
            "import": {
                "autotag": True,
                "copy": False,
                "write": True,
                "quiet": True,
                "incremental": False,
            },
            "plugins": ["musicbrainz", "lastgenre"],
            "lastgenre": {
                "auto": True,
                "canonical": True,
                "count": 2,
            },
        }

        # Create a temporary config file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as temp_config:
            yaml.dump(beets_config, temp_config)
            temp_config_path = temp_config.name

        try:
            # Run beets import
            # We use --quiet and --noincremental to ensure it doesn't prompt for input
            beet_path = os.environ.get("BEETS_PATH", "beet")
            cmd = [
                beet_path,
                "-c",
                temp_config_path,
                "import",
                "-q",
                "-s",  # Treat as a single track (singleton)
                track_path,
            ]
            
            self.to_screen(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                self.to_screen(f"Beets error: {result.stderr}")
            else:
                self.to_screen("Beets processing completed successfully")

        except Exception as e:
            self.to_screen(f"Failed to run beets: {str(e)}")
        finally:
            # Clean up temporary config file
            if os.path.exists(temp_config_path):
                os.remove(temp_config_path)

        return [], information
