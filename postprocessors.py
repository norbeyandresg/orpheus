import os
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

        # Update downloaded file name
        src = f"{self.library_path}/{information.get('id')}.mp3"
        dst = f"{self.library_path}/{information.get('title', '').replace('/', '-')} [{information.get('id')}].mp3"
        os.rename(src, dst)

        return [], information
