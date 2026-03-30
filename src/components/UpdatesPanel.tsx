import { callable } from "@decky/api"
import { ButtonItem, Field, PanelSection, PanelSectionRow } from "@decky/ui"
import { useEffect, useRef, useState } from "react"

const getLatestVersionNum = callable<[], string>("get_latest_version_num")
const otaUpdate = callable<[], boolean>("ota_update")

type Props = {
  installedVersionNum: string
}

const UpdatesPanel = ({ installedVersionNum }: Props) => {
  const [latestVersionNum, setLatestVersionNum] = useState("")
  const [latestVersionError, setLatestVersionError] = useState<string | null>(null)
  const [updateError, setUpdateError] = useState<string | null>(null)
  const [isLoadingLatestVersion, setIsLoadingLatestVersion] = useState(false)
  const [isUpdating, setIsUpdating] = useState(false)
  const isMountedRef = useRef(true)

  const loadLatestVersion = async () => {
    setIsLoadingLatestVersion(true)
    setLatestVersionError(null)
    try {
      const fetchedVersionNum = await getLatestVersionNum()
      if (!isMountedRef.current) {
        return
      }

      setLatestVersionNum(fetchedVersionNum)
    } catch {
      if (!isMountedRef.current) {
        return
      }

      setLatestVersionNum("")
      setLatestVersionError("Failed to fetch the latest version.")
    } finally {
      if (isMountedRef.current) {
        setIsLoadingLatestVersion(false)
      }
    }
  }

  useEffect(() => {
    void loadLatestVersion()

    return () => {
      isMountedRef.current = false
    }
  }, [])

  let buttonText = `Update to ${latestVersionNum}`

  if (installedVersionNum === latestVersionNum && Boolean(latestVersionNum)) {
    buttonText = "Reinstall Plugin"
  }

  const handleUpdate = async () => {
    setIsUpdating(true)
    setUpdateError(null)
    try {
      const success = await otaUpdate()
      if (!success) {
        setUpdateError("Failed to update DeckyZone.")
      }
    } catch {
      setUpdateError("Failed to update DeckyZone.")
    } finally {
      setIsUpdating(false)
    }
  }

  return (
    <PanelSection title="Updates">
      <PanelSectionRow>
        <Field label="Installed Version">{installedVersionNum || "Unknown"}</Field>
      </PanelSectionRow>
      {Boolean(latestVersionNum) && (
        <PanelSectionRow>
          <Field label="Latest Version">{latestVersionNum}</Field>
        </PanelSectionRow>
      )}
      {latestVersionError && (
        <>
          <PanelSectionRow>
            <div style={{ color: "red" }}>{latestVersionError}</div>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={() => void loadLatestVersion()} disabled={isLoadingLatestVersion}>
              Retry
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}
      {updateError && (
        <>
          <PanelSectionRow>
            <div style={{ color: "red" }}>{updateError}</div>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={() => void handleUpdate()} disabled={isUpdating}>
              Retry
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}
      {Boolean(latestVersionNum) && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => void handleUpdate()} disabled={isUpdating}>
            {isUpdating ? "Updating..." : buttonText}
          </ButtonItem>
        </PanelSectionRow>
      )}
    </PanelSection>
  )
}

export default UpdatesPanel
