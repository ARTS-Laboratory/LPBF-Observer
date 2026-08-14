from __future__ import annotations

import json


class MetadataWriter:

    def __init__(
        self,
        session,
        camera_information,
        received_format,
        codec,
        fps,
    ):

        self.session = session
        self.camera_information = camera_information
        self.received_format = received_format
        self.codec = codec
        self.fps = fps

    def update(
        self,
        status: str,
        stats,
    ):

        metadata = self._build_json(
            status,
            stats,
        )

        self.session.metadata_path.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )