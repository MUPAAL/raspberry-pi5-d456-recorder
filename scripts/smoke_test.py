#!/usr/bin/env python3
"""Verify simultaneous D456 depth, color, and left-infrared streaming."""

import numpy as np
import pyrealsense2 as rs


def main():
    pipeline = rs.pipeline()
    # The D435 has no 5 FPS mode; fall back to 15 FPS.
    for fps in (5, 15):
        config = rs.config()
        config.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, fps)
        config.enable_stream(rs.stream.color, 848, 480, rs.format.bgr8, fps)
        config.enable_stream(rs.stream.infrared, 1, 848, 480, rs.format.y8, fps)
        try:
            profile = pipeline.start(config)
            break
        except RuntimeError:
            if fps == 15:
                raise

    try:
        frames = None
        for _ in range(30):
            frames = pipeline.wait_for_frames(10000)

        depth = frames.get_depth_frame()
        color = frames.get_color_frame()
        infrared = frames.get_infrared_frame(1)
        device = profile.get_device()

        print("Camera:", device.get_info(rs.camera_info.name))
        print("Depth:", bool(depth))
        print("Color:", bool(color))
        print("Infrared 1:", bool(infrared))

        if depth:
            image = np.asanyarray(depth.get_data())
            valid = image[image > 0]
            scale = device.first_depth_sensor().get_depth_scale()
            print("Valid depth pixels:", len(valid), "/", image.size)
            if len(valid):
                print("Median depth:", float(np.median(valid)) * scale, "m")
            print("Center depth:", depth.get_distance(424, 240), "m")
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()

