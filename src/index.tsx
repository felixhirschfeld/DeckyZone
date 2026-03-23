import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin } from "@decky/api";
import { useEffect, useState } from "react";
import { FaSlidersH } from "react-icons/fa";

type PluginStatus = {
  state: string;
  message: string;
};

const getStatus = callable<[], PluginStatus>("get_status");
const reapplyStartupMode = callable<[], PluginStatus>("reapply_startup_mode");

function Content() {
  const [status, setStatus] = useState<PluginStatus>({
    state: "loading",
    message: "Loading DeckyZone status.",
  });
  const [working, setWorking] = useState(false);

  const loadStatus = async () => {
    try {
      const nextStatus = await getStatus();
      setStatus(nextStatus);
    } catch (error) {
      setStatus({
        state: "failed",
        message: `Failed to load status: ${String(error)}`,
      });
    }
  };

  const handleReapply = async () => {
    setWorking(true);
    try {
      const nextStatus = await reapplyStartupMode();
      setStatus(nextStatus);
    } catch (error) {
      setStatus({
        state: "failed",
        message: `Failed to reapply startup mode: ${String(error)}`,
      });
    } finally {
      setWorking(false);
    }
  };

  useEffect(() => {
    void loadStatus();
  }, []);

  return (
    <PanelSection title="Startup Mode">
      <PanelSectionRow>
        <div>
          <div>
            <strong>State:</strong> {status.state}
          </div>
          <div>{status.message}</div>
        </div>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={() => void handleReapply()} disabled={working}>
          {working ? "Applying Startup Mode..." : "Reapply Startup Mode"}
        </ButtonItem>
      </PanelSectionRow>
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
