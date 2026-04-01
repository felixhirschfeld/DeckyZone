import { callable } from '@decky/api'
import { DialogButton, Field, ModalRoot, PanelSection, PanelSectionRow, SteamSpinner, gamepadDialogClasses } from '@decky/ui'
import { useEffect, useRef, useState } from 'react'
import type { DebugInfoSnapshot } from '../types/plugin'

const getDebugInfo = callable<[], DebugInfoSnapshot>('get_debug_info')

type Props = {
  closeModal?: () => void
}

type SnapshotRowProps = {
  label: string
  value: string
}

type PathRowProps = {
  path: string
}

const sectionBodyStyle = {
  maxHeight: '70vh',
  overflowY: 'auto' as const,
  padding: '0 12px 12px',
}

const pathRowStyle = {
  overflowX: 'auto' as const,
  overflowY: 'hidden' as const,
}

const pathTextStyle = {
  fontFamily: 'monospace',
  whiteSpace: 'nowrap' as const,
  display: 'inline-block',
}

const SnapshotRow = ({ label, value }: SnapshotRowProps) => {
  return (
    <PanelSectionRow>
      <Field label={label} highlightOnFocus={false}>
        {value}
      </Field>
    </PanelSectionRow>
  )
}

const PathRow = ({ path }: PathRowProps) => {
  return (
    <PanelSectionRow>
      <div className={gamepadDialogClasses.FieldDescription} style={pathRowStyle}>
        <span style={pathTextStyle}>{path}</span>
      </div>
    </PanelSectionRow>
  )
}

const formatValue = (value: string | null | undefined) => {
  return value ? value : 'Unavailable'
}

const formatBoolean = (value: boolean) => {
  return value ? 'Yes' : 'No'
}

const DebugInfoModal = ({ closeModal }: Props) => {
  const [snapshot, setSnapshot] = useState<DebugInfoSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const isMountedRef = useRef(true)

  const loadDebugInfo = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const nextSnapshot = await getDebugInfo()
      if (!isMountedRef.current) {
        return
      }

      setSnapshot(nextSnapshot)
    } catch (error) {
      if (!isMountedRef.current) {
        return
      }

      setError(`Failed to load debug info: ${String(error)}`)
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false)
      }
    }
  }

  useEffect(() => {
    void loadDebugInfo()

    return () => {
      isMountedRef.current = false
    }
  }, [])

  return (
    <ModalRoot closeModal={closeModal}>
      <div style={sectionBodyStyle}>
        <PanelSection title="Debug Info">
          <PanelSectionRow>
            <DialogButton onClick={() => void loadDebugInfo()} disabled={isLoading}>
              Reload
            </DialogButton>
          </PanelSectionRow>
          {isLoading && !snapshot && (
            <PanelSectionRow>
              <SteamSpinner />
            </PanelSectionRow>
          )}
          {error && (
            <PanelSectionRow>
              <div style={{ color: 'red' }}>{error}</div>
            </PanelSectionRow>
          )}
        </PanelSection>

        {snapshot && (
          <>
            <PanelSection title="Device Identity">
              <SnapshotRow label="Vendor" value={formatValue(snapshot.deviceIdentity.vendorName)} />
              {snapshot.deviceIdentity.dmiPaths[0] && <PathRow path={snapshot.deviceIdentity.dmiPaths[0]} />}
              <SnapshotRow label="Product" value={formatValue(snapshot.deviceIdentity.productName)} />
              {snapshot.deviceIdentity.dmiPaths[1] && <PathRow path={snapshot.deviceIdentity.dmiPaths[1]} />}
              <SnapshotRow label="Board" value={formatValue(snapshot.deviceIdentity.boardName)} />
              {snapshot.deviceIdentity.dmiPaths[2] && <PathRow path={snapshot.deviceIdentity.dmiPaths[2]} />}
              <SnapshotRow label="Board Vendor" value={formatValue(snapshot.deviceIdentity.boardVendor)} />
              {snapshot.deviceIdentity.dmiPaths[3] && <PathRow path={snapshot.deviceIdentity.dmiPaths[3]} />}
              <SnapshotRow label="Supported Device" value={formatBoolean(snapshot.deviceIdentity.supportedDevice)} />
            </PanelSection>

            <PanelSection title="OS Context">
              <SnapshotRow label="Distro" value={formatValue(snapshot.osContext.prettyName)} />
              {snapshot.osContext.osReleaseCandidatePaths.map((path) => (
                <PathRow key={path} path={path} />
              ))}
              <SnapshotRow label="Kernel Release" value={formatValue(snapshot.osContext.kernelRelease)} />
            </PanelSection>

            <PanelSection title="InputPlumber">
              <SnapshotRow label="Available" value={formatBoolean(snapshot.inputPlumber.available)} />
              <PathRow path={snapshot.inputPlumber.compositeDeviceObjectPath} />
              <SnapshotRow label="Profile Name" value={formatValue(snapshot.inputPlumber.profileName)} />
              <SnapshotRow label="Profile Path" value={formatValue(snapshot.inputPlumber.profilePath)} />
            </PanelSection>

            <PanelSection title="Zotac Zone Kernel Drivers">
              <SnapshotRow label="zotac_zone_platform" value={formatBoolean(snapshot.zotacZoneKernelDrivers.zotacZonePlatformLoaded)} />
              <PathRow path={snapshot.zotacZoneKernelDrivers.zotacZonePlatformPath} />
              <SnapshotRow label="zotac_zone_hid" value={formatBoolean(snapshot.zotacZoneKernelDrivers.zotacZoneHidLoaded)} />
              <PathRow path={snapshot.zotacZoneKernelDrivers.zotacZoneHidPath} />
              <SnapshotRow
                label="firmware_attributes_class"
                value={formatBoolean(snapshot.zotacZoneKernelDrivers.firmwareAttributesClassLoaded)}
              />
              <PathRow path={snapshot.zotacZoneKernelDrivers.firmwareAttributesClassPath} />
              <SnapshotRow
                label="Firmware Attributes Node"
                value={formatBoolean(snapshot.zotacZoneKernelDrivers.firmwareAttributesNodePresent)}
              />
              <PathRow path={snapshot.zotacZoneKernelDrivers.firmwareAttributesNodePath} />
              <SnapshotRow label="Zotac HID sysfs config node" value={formatValue(snapshot.zotacZoneKernelDrivers.hidConfigNodePath)} />
              <PathRow path={snapshot.zotacZoneKernelDrivers.hidConfigSearchRoot} />
            </PanelSection>

            <PanelSection title="Gamescope">
              <SnapshotRow label="Built-in Zotac OLED Profile" value={formatBoolean(snapshot.gamescope.builtInAvailable)} />
              {snapshot.gamescope.builtInCandidatePaths.map((path) => (
                <PathRow key={path} path={path} />
              ))}
              <SnapshotRow label="Managed DeckyZone Profile" value={formatBoolean(snapshot.gamescope.managedProfileInstalled)} />
              <PathRow path={snapshot.gamescope.managedProfilePath} />
              <SnapshotRow label="Green Tint Fix" value={formatBoolean(snapshot.gamescope.greenTintFixEnabled)} />
              <SnapshotRow label="Managed Profile State" value={formatValue(snapshot.gamescope.verificationState)} />
            </PanelSection>

            <PanelSection title="DeckyZone Status">
              <SnapshotRow label="Current Status" value={formatValue(snapshot.deckyZoneStatus.message)} />
            </PanelSection>
          </>
        )}
      </div>
    </ModalRoot>
  )
}

export default DebugInfoModal
