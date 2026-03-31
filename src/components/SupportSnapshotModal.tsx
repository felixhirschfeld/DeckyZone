import { callable } from '@decky/api'
import {
  DialogButton,
  Field,
  ModalRoot,
  PanelSection,
  PanelSectionRow,
  SteamSpinner,
  gamepadDialogClasses,
} from '@decky/ui'
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { SupportSnapshot } from '../types/plugin'

const getSupportSnapshot = callable<[], SupportSnapshot>('get_support_snapshot')

type Props = {
  closeModal?: () => void
}

type SnapshotRowProps = {
  label: string
  value: string
}

type HintRowProps = {
  children: ReactNode
}

type PathHintRowProps = {
  label: string
  path: string
}

type PathsHintRowProps = {
  label: string
  paths: string[]
}

const sectionBodyStyle = {
  maxHeight: '70vh',
  overflowY: 'auto' as const,
  padding: '0 12px 12px',
}

const pathTextStyle = {
  fontFamily: 'monospace',
  overflowWrap: 'anywhere' as const,
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

const HintRow = ({ children }: HintRowProps) => {
  return (
    <PanelSectionRow>
      <div className={gamepadDialogClasses.FieldDescription}>{children}</div>
    </PanelSectionRow>
  )
}

const PathText = ({ path }: { path: string }) => {
  return <span style={pathTextStyle}>{path}</span>
}

const PathsHintRow = ({ label, paths }: PathsHintRowProps) => {
  return (
    <HintRow>
      <div>{label}</div>
      {paths.map((path) => (
        <div key={path}>
          <PathText path={path} />
        </div>
      ))}
    </HintRow>
  )
}

const PathHintRow = ({ label, path }: PathHintRowProps) => {
  return (
    <HintRow>
      <div>{label}</div>
      <div>
        <PathText path={path} />
      </div>
    </HintRow>
  )
}

const formatValue = (value: string | null | undefined) => {
  return value ? value : 'Unavailable'
}

const formatBoolean = (value: boolean) => {
  return value ? 'Yes' : 'No'
}

const SupportSnapshotModal = ({ closeModal }: Props) => {
  const [snapshot, setSnapshot] = useState<SupportSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const isMountedRef = useRef(true)

  const loadSnapshot = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const nextSnapshot = await getSupportSnapshot()
      if (!isMountedRef.current) {
        return
      }

      setSnapshot(nextSnapshot)
    } catch (error) {
      if (!isMountedRef.current) {
        return
      }

      setError(`Failed to load support snapshot: ${String(error)}`)
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false)
      }
    }
  }

  useEffect(() => {
    void loadSnapshot()

    return () => {
      isMountedRef.current = false
    }
  }, [])

  return (
    <ModalRoot closeModal={closeModal}>
      <div style={sectionBodyStyle}>
        <PanelSection title="Support Snapshot">
          <PanelSectionRow>
            <DialogButton onClick={() => void loadSnapshot()} disabled={isLoading}>
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
              <SnapshotRow label="Product" value={formatValue(snapshot.deviceIdentity.productName)} />
              <SnapshotRow label="Board" value={formatValue(snapshot.deviceIdentity.boardName)} />
              <SnapshotRow label="Board Vendor" value={formatValue(snapshot.deviceIdentity.boardVendor)} />
              <SnapshotRow label="Supported Device" value={formatBoolean(snapshot.deviceIdentity.supportedDevice)} />
              <PathsHintRow label="Reads:" paths={snapshot.deviceIdentity.dmiPaths} />
            </PanelSection>

            <PanelSection title="OS Context">
              <SnapshotRow label="Distro" value={formatValue(snapshot.osContext.prettyName)} />
              <SnapshotRow label="Kernel Release" value={formatValue(snapshot.osContext.kernelRelease)} />
              <PathsHintRow label="Reads:" paths={snapshot.osContext.osReleaseCandidatePaths} />
            </PanelSection>

            <PanelSection title="InputPlumber">
              <SnapshotRow label="Available" value={formatBoolean(snapshot.inputPlumber.available)} />
              <SnapshotRow label="Profile Name" value={formatValue(snapshot.inputPlumber.profileName)} />
              <SnapshotRow label="Profile Path" value={formatValue(snapshot.inputPlumber.profilePath)} />
              <PathHintRow label="D-Bus object:" path={snapshot.inputPlumber.compositeDeviceObjectPath} />
            </PanelSection>

            <PanelSection title="Zotac Zone Kernel Drivers">
              <SnapshotRow
                label="zotac_zone_platform"
                value={formatBoolean(snapshot.zotacZoneKernelDrivers.zotacZonePlatformLoaded)}
              />
              <PathHintRow label="Checks:" path={snapshot.zotacZoneKernelDrivers.zotacZonePlatformPath} />
              <SnapshotRow
                label="zotac_zone_hid"
                value={formatBoolean(snapshot.zotacZoneKernelDrivers.zotacZoneHidLoaded)}
              />
              <PathHintRow label="Checks:" path={snapshot.zotacZoneKernelDrivers.zotacZoneHidPath} />
              <SnapshotRow
                label="firmware_attributes_class"
                value={formatBoolean(snapshot.zotacZoneKernelDrivers.firmwareAttributesClassLoaded)}
              />
              <PathHintRow
                label="Checks:"
                path={snapshot.zotacZoneKernelDrivers.firmwareAttributesClassPath}
              />
              <SnapshotRow
                label="Firmware Attributes Node"
                value={formatBoolean(snapshot.zotacZoneKernelDrivers.firmwareAttributesNodePresent)}
              />
              <PathHintRow
                label="Checks:"
                path={snapshot.zotacZoneKernelDrivers.firmwareAttributesNodePath}
              />
              <SnapshotRow
                label="Zotac HID sysfs config node"
                value={formatValue(snapshot.zotacZoneKernelDrivers.hidConfigNodePath)}
              />
              <HintRow>
                <div>Scans:</div>
                <div>
                  <PathText path={snapshot.zotacZoneKernelDrivers.hidConfigSearchRoot} />
                </div>
                <div>
                  Match file: <PathText path={snapshot.zotacZoneKernelDrivers.hidConfigMatchMarker} />
                </div>
              </HintRow>
            </PanelSection>

            <PanelSection title="Gamescope">
              <SnapshotRow
                label="Built-in Zotac OLED Profile"
                value={formatBoolean(snapshot.gamescope.builtInAvailable)}
              />
              <PathsHintRow label="Candidate paths:" paths={snapshot.gamescope.builtInCandidatePaths} />
              <SnapshotRow
                label="Managed DeckyZone Profile"
                value={formatBoolean(snapshot.gamescope.managedProfileInstalled)}
              />
              <PathHintRow label="Managed path:" path={snapshot.gamescope.managedProfilePath} />
              <SnapshotRow
                label="Green Tint Fix"
                value={formatBoolean(snapshot.gamescope.greenTintFixEnabled)}
              />
              <SnapshotRow
                label="Managed Profile State"
                value={formatValue(snapshot.gamescope.verificationState)}
              />
              <PathsHintRow
                label="Legacy managed paths:"
                paths={[
                  snapshot.gamescope.legacyManagedBaseProfilePath,
                  snapshot.gamescope.legacyManagedGreenTintProfilePath,
                ]}
              />
              <PathsHintRow
                label="Plugin asset files:"
                paths={[
                  snapshot.gamescope.assetBaseProfilePath,
                  snapshot.gamescope.assetGreenTintProfilePath,
                ]}
              />
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

export default SupportSnapshotModal
