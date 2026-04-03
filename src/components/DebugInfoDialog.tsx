import { callable } from '@decky/api'
import {
  ControlsList,
  DialogBody,
  DialogButton,
  DialogControlsSection,
  DialogControlsSectionHeader,
  DialogFooter,
  Field,
  ModalRoot,
  SteamSpinner,
  Tabs,
  gamepadDialogClasses,
} from '@decky/ui'
import { type ReactNode, useEffect, useRef, useState } from 'react'
import type { DebugInfoSnapshot } from '../types/plugin'

const getDebugInfo = callable<[], DebugInfoSnapshot>('get_debug_info')

type Props = {
  closeModal?: () => void
}

type SnapshotRowProps = {
  label: string
  value: string
  description?: ReactNode
  bottomSeparator?: 'standard' | 'thick' | 'none'
}

type PathListProps = {
  label: string
  paths: string[]
  bottomSeparator?: 'standard' | 'thick' | 'none'
}

const bodyStyle = {
  display: 'flex',
  flexDirection: 'column' as const,
  gap: '12px',
  padding: '0 12px 12px',
}

const tabsHostStyle = {
  width: '100%',
  height: '60vh',
  minHeight: '60vh',
  overflow: 'hidden' as const,
}

const tabContentStyle = {
  boxSizing: 'border-box' as const,
  height: '100%',
  overflowY: 'auto' as const,
  padding: '8px 4px 0 0',
}

const pathListStyle = {
  display: 'grid',
  gap: '6px',
}

const pathTextStyle = {
  fontFamily: 'monospace',
  whiteSpace: 'nowrap' as const,
  display: 'inline-block',
}

const PathText = ({ path }: { path: string }) => {
  return (
    <div className={gamepadDialogClasses.FieldDescription}>
      <span style={pathTextStyle}>{path}</span>
    </div>
  )
}

const SnapshotRow = ({ label, value, description, bottomSeparator = 'standard' }: SnapshotRowProps) => {
  return (
    <Field label={label} highlightOnFocus={false} description={description} bottomSeparator={bottomSeparator}>
      {value}
    </Field>
  )
}

const PathList = ({ label, paths, bottomSeparator = 'standard' }: PathListProps) => {
  return (
    <Field label={label} highlightOnFocus={false} bottomSeparator={bottomSeparator}>
      <div style={pathListStyle}>
        {paths.map((path) => (
          <PathText key={path} path={path} />
        ))}
      </div>
    </Field>
  )
}

const formatValue = (value: string | null | undefined) => {
  return value ? value : 'Unavailable'
}

const formatBoolean = (value: boolean) => {
  return value ? 'Yes' : 'No'
}

const TabContent = ({ children }: { children: ReactNode }) => {
  return <div style={tabContentStyle}>{children}</div>
}

const DebugInfoDialog = ({ closeModal }: Props) => {
  const [snapshot, setSnapshot] = useState<DebugInfoSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')
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
      <DialogBody style={bodyStyle}>
        {isLoading && !snapshot && <SteamSpinner />}
        {error && <div style={{ color: 'red', marginBottom: snapshot ? '12px' : 0 }}>{error}</div>}
        {snapshot && (
          <div style={tabsHostStyle}>
            <Tabs
              activeTab={activeTab}
              onShowTab={setActiveTab}
              autoFocusContents
              tabs={[
                {
                  id: 'overview',
                  title: 'Overview',
                  content: (
                    <TabContent>
                      <DialogControlsSection>
                        <DialogControlsSectionHeader>Device Identity</DialogControlsSectionHeader>
                        <SnapshotRow
                          label="Vendor"
                          value={formatValue(snapshot.deviceIdentity.vendorName)}
                          description={snapshot.deviceIdentity.dmiPaths[0] ? <PathText path={snapshot.deviceIdentity.dmiPaths[0]} /> : undefined}
                        />
                        <SnapshotRow
                          label="Product"
                          value={formatValue(snapshot.deviceIdentity.productName)}
                          description={snapshot.deviceIdentity.dmiPaths[1] ? <PathText path={snapshot.deviceIdentity.dmiPaths[1]} /> : undefined}
                        />
                        <SnapshotRow
                          label="Board"
                          value={formatValue(snapshot.deviceIdentity.boardName)}
                          description={snapshot.deviceIdentity.dmiPaths[2] ? <PathText path={snapshot.deviceIdentity.dmiPaths[2]} /> : undefined}
                        />
                        <SnapshotRow
                          label="Board Vendor"
                          value={formatValue(snapshot.deviceIdentity.boardVendor)}
                          description={snapshot.deviceIdentity.dmiPaths[3] ? <PathText path={snapshot.deviceIdentity.dmiPaths[3]} /> : undefined}
                        />
                        <SnapshotRow
                          label="Supported Device"
                          value={formatBoolean(snapshot.deviceIdentity.supportedDevice)}
                          bottomSeparator="none"
                        />
                      </DialogControlsSection>

                      <DialogControlsSection>
                        <DialogControlsSectionHeader>OS Context</DialogControlsSectionHeader>
                        <SnapshotRow label="Distro" value={formatValue(snapshot.osContext.prettyName)} />
                        <PathList label="os-release paths" paths={snapshot.osContext.osReleaseCandidatePaths} />
                        <SnapshotRow
                          label="Kernel Release"
                          value={formatValue(snapshot.osContext.kernelRelease)}
                          bottomSeparator="none"
                        />
                      </DialogControlsSection>

                      <DialogControlsSection>
                        <DialogControlsSectionHeader>DeckyZone Status</DialogControlsSectionHeader>
                        <SnapshotRow
                          label="Current Status"
                          value={formatValue(snapshot.deckyZoneStatus.message)}
                          bottomSeparator="none"
                        />
                      </DialogControlsSection>
                    </TabContent>
                  ),
                },
                {
                  id: 'input',
                  title: 'Input',
                  content: (
                    <TabContent>
                      <DialogControlsSection>
                        <DialogControlsSectionHeader>InputPlumber</DialogControlsSectionHeader>
                        <SnapshotRow label="Available" value={formatBoolean(snapshot.inputPlumber.available)} />
                        <SnapshotRow
                          label="Composite Device Object"
                          value={snapshot.inputPlumber.compositeDeviceObjectPath}
                        />
                        <SnapshotRow label="Profile Name" value={formatValue(snapshot.inputPlumber.profileName)} />
                        <SnapshotRow
                          label="Profile Path"
                          value={formatValue(snapshot.inputPlumber.profilePath)}
                          bottomSeparator="none"
                        />
                      </DialogControlsSection>

                      <DialogControlsSection>
                        <DialogControlsSectionHeader>Controller HID</DialogControlsSectionHeader>
                        <SnapshotRow
                          label="Zotac HID sysfs config node"
                          value={formatValue(snapshot.zotacZoneKernelDrivers.hidConfigNodePath)}
                        />
                        <SnapshotRow
                          label="Search Root"
                          value={snapshot.zotacZoneKernelDrivers.hidConfigSearchRoot}
                          bottomSeparator="none"
                        />
                      </DialogControlsSection>
                    </TabContent>
                  ),
                },
                {
                  id: 'kernel',
                  title: 'Kernel',
                  content: (
                    <TabContent>
                      <DialogControlsSection>
                        <DialogControlsSectionHeader>Zotac Zone Kernel Drivers</DialogControlsSectionHeader>
                        <SnapshotRow
                          label="zotac_zone_platform"
                          value={formatBoolean(snapshot.zotacZoneKernelDrivers.zotacZonePlatformLoaded)}
                          description={<PathText path={snapshot.zotacZoneKernelDrivers.zotacZonePlatformPath} />}
                        />
                        <SnapshotRow
                          label="zotac_zone_hid"
                          value={formatBoolean(snapshot.zotacZoneKernelDrivers.zotacZoneHidLoaded)}
                          description={<PathText path={snapshot.zotacZoneKernelDrivers.zotacZoneHidPath} />}
                        />
                        <SnapshotRow
                          label="firmware_attributes_class"
                          value={formatBoolean(snapshot.zotacZoneKernelDrivers.firmwareAttributesClassLoaded)}
                          description={<PathText path={snapshot.zotacZoneKernelDrivers.firmwareAttributesClassPath} />}
                        />
                        <SnapshotRow
                          label="Firmware Attributes Node"
                          value={formatBoolean(snapshot.zotacZoneKernelDrivers.firmwareAttributesNodePresent)}
                          description={<PathText path={snapshot.zotacZoneKernelDrivers.firmwareAttributesNodePath} />}
                          bottomSeparator="none"
                        />
                      </DialogControlsSection>
                    </TabContent>
                  ),
                },
                {
                  id: 'display',
                  title: 'Display',
                  content: (
                    <TabContent>
                      <DialogControlsSection>
                        <DialogControlsSectionHeader>Gamescope</DialogControlsSectionHeader>
                        <SnapshotRow
                          label="Built-in Zotac OLED Profile"
                          value={formatBoolean(snapshot.gamescope.builtInAvailable)}
                        />
                        <PathList label="Built-in Candidate Paths" paths={snapshot.gamescope.builtInCandidatePaths} />
                        <SnapshotRow
                          label="Managed DeckyZone Profile"
                          value={formatBoolean(snapshot.gamescope.managedProfileInstalled)}
                          description={<PathText path={snapshot.gamescope.managedProfilePath} />}
                        />
                        <SnapshotRow
                          label="Green Tint Fix"
                          value={formatBoolean(snapshot.gamescope.greenTintFixEnabled)}
                        />
                        <SnapshotRow
                          label="Verification State"
                          value={formatValue(snapshot.gamescope.verificationState)}
                        />
                        <SnapshotRow
                          label="Base Profile Asset"
                          value={formatBoolean(snapshot.gamescope.baseAssetAvailable)}
                          description={<PathText path={snapshot.gamescope.baseAssetPath} />}
                        />
                        <SnapshotRow
                          label="Green Tint Asset"
                          value={formatBoolean(snapshot.gamescope.greenTintAssetAvailable)}
                          description={<PathText path={snapshot.gamescope.greenTintAssetPath} />}
                          bottomSeparator="none"
                        />
                      </DialogControlsSection>
                    </TabContent>
                  ),
                },
              ]}
            />
          </div>
        )}
      </DialogBody>
      <DialogFooter>
        <ControlsList>
          <DialogButton onClick={() => void loadDebugInfo()} disabled={isLoading} style={{ height: '100%' }}>
            {isLoading ? 'Reloading' : 'Reload'}
          </DialogButton>
        </ControlsList>
      </DialogFooter>
    </ModalRoot>
  )
}

export default DebugInfoDialog
