import { Composition } from "remotion";
import {
  CURRENT_STATE_DURATION_FRAMES,
  CURRENT_STATE_FPS,
  ShellCurrentStateDemo,
} from "./ShellCurrentStateDemo";
import { ShellInstagramReel } from "./ShellInstagramReel";

export const FPS = 30;
export const DURATION_SECONDS = 60;

export const RemotionRoot = () => {
  return (
    <>
      <Composition
        id="ShellInstagramReel"
        component={ShellInstagramReel}
        durationInFrames={FPS * DURATION_SECONDS}
        fps={FPS}
        height={1920}
        width={1080}
      />
      <Composition
        id="ShellCurrentStateDemo"
        component={ShellCurrentStateDemo}
        durationInFrames={CURRENT_STATE_DURATION_FRAMES}
        fps={CURRENT_STATE_FPS}
        height={1280}
        width={720}
      />
    </>
  );
};
