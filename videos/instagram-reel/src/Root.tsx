import { Composition } from "remotion";
import {
  CURRENT_STATE_DURATION_FRAMES,
  CURRENT_STATE_FPS,
  ShellCurrentStateDemo,
} from "./ShellCurrentStateDemo";
import {
  CURRENT_UI_LANDSCAPE_DURATION_FRAMES,
  CURRENT_UI_LANDSCAPE_FPS,
  ShellCurrentUiLandscape,
} from "./ShellCurrentUiLandscape";
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
      <Composition
        id="ShellCurrentUiLandscape"
        component={ShellCurrentUiLandscape}
        durationInFrames={CURRENT_UI_LANDSCAPE_DURATION_FRAMES}
        fps={CURRENT_UI_LANDSCAPE_FPS}
        height={1080}
        width={1920}
      />
    </>
  );
};
