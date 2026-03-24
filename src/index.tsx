import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  SliderField,
  staticClasses,
  ToggleField,
} from "@decky/ui";
import { callable, definePlugin } from "@decky/api";
import { useEffect, useRef, useState } from "react";
import { FaSlidersH } from "react-icons/fa";

type PluginStatus = {
  state: string;
  message: string;
};

type PluginSettings = {
  startupApplyEnabled: boolean;
  inputplumberAvailable: boolean;
  rumbleEnabled: boolean;
  rumbleIntensity: number;
  rumbleAvailable: boolean;
};

const getStatus = callable<[], PluginStatus>("get_status");
const getSettings = callable<[], PluginSettings>("get_settings");
const setStartupApplyEnabled = callable<[boolean], PluginSettings>(
  "set_startup_apply_enabled"
);
const setRumbleEnabled = callable<[boolean], PluginSettings>("set_rumble_enabled");
const setRumbleIntensity = callable<[number], PluginSettings>(
  "set_rumble_intensity"
);
const testRumble = callable<[], boolean>("test_rumble");

const DEFAULT_STARTUP_DESCRIPTION =
  "Restores the Zotac Steam Deck-style controller targets after boot.";
const DEFAULT_RUMBLE_DESCRIPTION =
  "Keeps reapplying your preferred vibration intensity to prevent other services from overriding it.";
const RUMBLE_UNAVAILABLE_MESSAGE =
  "Rumble device is not available.";

function getStartupDescription(status: PluginStatus, settings: PluginSettings) {
  if (!settings.inputplumberAvailable) {
    return "InputPlumber is not available.";
  }

  if (
    status.state === "failed" ||
    status.state === "disabled" ||
    status.state === "unsupported"
  ) {
    return status.message;
  }

  return DEFAULT_STARTUP_DESCRIPTION;
}

function getRumbleDescription(
  settings: PluginSettings
) {
  if (!settings.rumbleAvailable) {
    return RUMBLE_UNAVAILABLE_MESSAGE;
  }

  return DEFAULT_RUMBLE_DESCRIPTION;
}

function Content() {
  const [status, setStatus] = useState<PluginStatus>({
    state: "loading",
    message: "Loading DeckyZone status.",
  });
  const [settings, setSettings] = useState<PluginSettings>({
    startupApplyEnabled: true,
    inputplumberAvailable: true,
    rumbleEnabled: true,
    rumbleIntensity: 75,
    rumbleAvailable: true,
  });
  const [rumbleIntensityDraft, setRumbleIntensityDraft] = useState(75);
  const [savingStartup, setSavingStartup] = useState(false);
  const [savingRumble, setSavingRumble] = useState(false);
  const [testingRumble, setTestingRumble] = useState(false);
  const [rumbleMessage, setRumbleMessage] = useState<string | null>(null);
  const [rumbleMessageKind, setRumbleMessageKind] = useState<
    "success" | "error" | null
  >(null);
  const rumbleIntensityLatestValue = useRef(75);
  const rumbleIntensitySaveTimeout = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );

  const clearPendingRumbleIntensitySave = () => {
    if (rumbleIntensitySaveTimeout.current !== null) {
      clearTimeout(rumbleIntensitySaveTimeout.current);
      rumbleIntensitySaveTimeout.current = null;
    }
  };

  const loadStatus = async () => {
    const nextStatus = await getStatus();
    setStatus(nextStatus);
  };

  const loadAll = async () => {
    try {
      const [nextStatus, nextSettings] = await Promise.all([
        getStatus(),
        getSettings(),
      ]);
      setStatus(nextStatus);
      setSettings(nextSettings);
      setRumbleIntensityDraft(nextSettings.rumbleIntensity);
      rumbleIntensityLatestValue.current = nextSettings.rumbleIntensity;
      if (!nextSettings.rumbleAvailable) {
        setRumbleMessage(null);
        setRumbleMessageKind(null);
      }
    } catch (error) {
      setStatus({
        state: "failed",
        message: `Failed to load plugin state: ${String(error)}`,
      });
    }
  };

  const handleStartupToggleChange = async (enabled: boolean) => {
    setSavingStartup(true);
    try {
      const nextSettings = await setStartupApplyEnabled(enabled);
      setSettings(nextSettings);
      await loadStatus();
    } catch (error) {
      setStatus({
        state: "failed",
        message: `Failed to update startup setting: ${String(error)}`,
      });
    } finally {
      setSavingStartup(false);
    }
  };

  const handleRumbleToggleChange = async (enabled: boolean) => {
    if (!enabled) {
      clearPendingRumbleIntensitySave();
    }

    setSavingRumble(true);
    try {
      const nextSettings = await setRumbleEnabled(enabled);
      setSettings(nextSettings);
      setRumbleIntensityDraft(nextSettings.rumbleIntensity);
      rumbleIntensityLatestValue.current = nextSettings.rumbleIntensity;
      setRumbleMessage(null);
      setRumbleMessageKind(null);
      await loadStatus();
    } catch (error) {
      setStatus({
        state: "failed",
        message: `Failed to update rumble setting: ${String(error)}`,
      });
    } finally {
      setSavingRumble(false);
    }
  };

  const saveRumbleIntensity = async (value: number) => {
    try {
      const nextSettings = await setRumbleIntensity(value);
      setSettings((currentSettings) => ({
        ...currentSettings,
        rumbleIntensity: nextSettings.rumbleIntensity,
        rumbleAvailable: nextSettings.rumbleAvailable,
      }));
      setRumbleMessage(null);
      setRumbleMessageKind(null);
    } catch (error) {
      setStatus({
        state: "failed",
        message: `Failed to update vibration intensity: ${String(error)}`,
      });
    }
  };

  const handleRumbleIntensityChange = (value: number) => {
    setRumbleIntensityDraft(value);
    rumbleIntensityLatestValue.current = value;
    clearPendingRumbleIntensitySave();
    rumbleIntensitySaveTimeout.current = setTimeout(() => {
      rumbleIntensitySaveTimeout.current = null;
      void saveRumbleIntensity(rumbleIntensityLatestValue.current);
    }, 500);
  };

  const handleTestRumble = async () => {
    clearPendingRumbleIntensitySave();
    setTestingRumble(true);
    setRumbleMessage(null);
    setRumbleMessageKind(null);
    try {
      const success = await testRumble();
      setRumbleMessage(
        success ? "Sent a test rumble event." : "Failed to send a test rumble event."
      );
      setRumbleMessageKind(success ? "success" : "error");
    } catch (error) {
      setRumbleMessage(`Failed to send a test rumble event: ${String(error)}`);
      setRumbleMessageKind("error");
    } finally {
      setTestingRumble(false);
    }
  };

  useEffect(() => {
    void loadAll();
    return () => {
      clearPendingRumbleIntensitySave();
    };
  }, []);

  return (
    <PanelSection title="Controller">
      <PanelSectionRow>
        <ToggleField
          label="Startup Target"
          checked={settings.startupApplyEnabled}
          onChange={(value: boolean) => void handleStartupToggleChange(value)}
          disabled={savingStartup}
          description={getStartupDescription(status, settings)}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label="Vibration Intensity"
          checked={settings.rumbleEnabled}
          onChange={(value: boolean) => void handleRumbleToggleChange(value)}
          disabled={savingRumble}
          description={getRumbleDescription(settings)}
        />
      </PanelSectionRow>
      {settings.rumbleEnabled && (
        <>
          <PanelSectionRow>
            <SliderField
              label="Vibration intensity"
              value={rumbleIntensityDraft}
              min={0}
              max={100}
              step={5}
              showValue
              notchTicksVisible
              onChange={handleRumbleIntensityChange}
              disabled={savingRumble || !settings.rumbleEnabled || !settings.rumbleAvailable}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={() => void handleTestRumble()}
              disabled={
                savingRumble ||
                testingRumble ||
                !settings.rumbleEnabled ||
                !settings.rumbleAvailable
              }
            >
              {testingRumble ? "Testing Rumble..." : "Test Rumble"}
            </ButtonItem>
          </PanelSectionRow>
          {rumbleMessage && (
            <PanelSectionRow>
              <div
                style={{
                  color: rumbleMessageKind === "error" ? "red" : undefined,
                }}
              >
                {rumbleMessage}
              </div>
            </PanelSectionRow>
          )}
        </>
      )}
    </PanelSection>
  );
}

export default definePlugin(() => {
  return {
    name: "DeckyZone",
    titleView: <div className={staticClasses.Title}>DeckyZone</div>,
    content: <Content />,
    icon: <FaSlidersH />,
    onDismount() {
      console.log("DeckyZone unloaded");
    },
  };
});
