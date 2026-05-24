import { Composition } from "remotion";
import {
  CURRENT_UI_LANDSCAPE_DURATION_FRAMES,
  CURRENT_UI_LANDSCAPE_FPS,
  ShellCurrentUiLandscape,
} from "./ShellCurrentUiLandscape";

export const RemotionRoot = () => {
  return (
    <>
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
