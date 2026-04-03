import { callable } from '@decky/api'
import {
  DialogBody,
  DialogControlsSection,
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

type PathDetailsProps = {
  paths: string[]
}

const bodyStyle = {
  display: 'flex',
  flexDirection: 'column' as const,
  gap: '8px',
  padding: '0 10px 0',
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
  padding: '0 2px 0 0',
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

const PathDetails = ({ paths }: PathDetailsProps) => {
  return (
    <div style={pathListStyle}>
      {paths.map((path) => (
        <PathText key={path} path={path} />
      ))}
    </div>
  )
}

const formatValue = (value: string | null | undefined) => {
  return value ? value : 'Unavailable'
}

const formatBoolean = (value: boolean) => {
  return value ? 'Yes' : 'No'
}

const isVerificationHealthy = (value: string | null | undefined) => {
  const normalized = (value ?? '').trim().toLowerCase()
  return normalized === 'ok' || normalized === 'healthy' || normalized === 'verified'
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
                        <SnapshotRow
                          label="Product"
                          value={formatValue(snapshot.deviceIdentity.productName)}
                        />
                        <SnapshotRow
                          label="Board"
                          value={formatValue(snapshot.deviceIdentity.boardName)}
                        />
                        <SnapshotRow
                          label="Distro"
                          value={formatValue(snapshot.osContext.prettyName)}
                        />
                        <SnapshotRow
                          label="Kernel"
                          value={formatValue(snapshot.osContext.kernelRelease)}
                        />
                        <SnapshotRow
                          label="DeckyZone Status"
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
                        <SnapshotRow label="Available" value={formatBoolean(snapshot.inputPlumber.available)} />
                        <SnapshotRow label="Profile Name" value={formatValue(snapshot.inputPlumber.profileName)} />
                        <SnapshotRow
                          label="Profile Path"
                          value={formatValue(snapshot.inputPlumber.profilePath)}
                        />
                        <SnapshotRow
                          label="Zotac HID sysfs config node"
                          value={formatValue(snapshot.zotacZoneKernelDrivers.hidConfigNodePath)}
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
                        <SnapshotRow
                          label="Built-in Profile"
                          value={formatBoolean(snapshot.gamescope.builtInAvailable)}
                          description={
                            !snapshot.gamescope.builtInAvailable && snapshot.gamescope.builtInCandidatePaths.length > 0 ? (
                              <PathDetails paths={snapshot.gamescope.builtInCandidatePaths} />
                            ) : undefined
                          }
                        />
                        <SnapshotRow
                          label="Managed Profile"
                          value={formatBoolean(snapshot.gamescope.managedProfileInstalled)}
                          description={
                            !snapshot.gamescope.managedProfileInstalled ? (
                              <PathDetails paths={[snapshot.gamescope.managedProfilePath]} />
                            ) : undefined
                          }
                        />
                        <SnapshotRow
                          label="Green Tint Fix"
                          value={formatBoolean(snapshot.gamescope.greenTintFixEnabled)}
                        />
                        <SnapshotRow
                          label="Verification State"
                          value={formatValue(snapshot.gamescope.verificationState)}
                          description={
                            !isVerificationHealthy(snapshot.gamescope.verificationState) ||
                            !snapshot.gamescope.baseAssetAvailable ||
                            !snapshot.gamescope.greenTintAssetAvailable ? (
                              <PathDetails
                                paths={[
                                  ...(!snapshot.gamescope.baseAssetAvailable ? [snapshot.gamescope.baseAssetPath] : []),
                                  ...(!snapshot.gamescope.greenTintAssetAvailable ? [snapshot.gamescope.greenTintAssetPath] : []),
                                ]}
                              />
                            ) : undefined
                          }
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
    </ModalRoot>
  )
}

export default DebugInfoDialog
