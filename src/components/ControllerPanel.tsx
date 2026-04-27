import { callable } from '@decky/api'
import { PanelSection } from '@decky/ui'
import { useEffect, useRef, useState } from 'react'
import ControllerTogglesPanel from './controller/ControllerTogglesPanel'
import PerGameSettingsPanel from './controller/PerGameSettingsPanel'
import RumblePanel from './controller/RumblePanel'
import TrackpadPanel from './controller/TrackpadPanel'
import type { ActiveGame, ControllerMode, PluginSettings, PluginStatus, TrackpadMode } from '../types/plugin'
import { useDeckyToastNotice } from '../utils/toasts'

type Props = {
  activeGame: ActiveGame | null
  settings: PluginSettings
  status: PluginStatus
  onSettingsChange: (nextSettings: PluginSettings) => void
  onStatusChange: (nextStatus: PluginStatus) => void
}

const getStatus = callable<[], PluginStatus>('get_status')
const setStartupApplyEnabled = callable<[boolean], PluginSettings>('set_startup_apply_enabled')
const setControllerMode = callable<[ControllerMode], PluginSettings>('set_controller_mode')
const setHomeButtonEnabled = callable<[boolean], PluginSettings>('set_home_button_enabled')
const setBrightnessDialFixEnabled = callable<[boolean], PluginSettings>('set_brightness_dial_fix_enabled')
const setTrackpadMode = callable<[TrackpadMode], PluginSettings>('set_trackpad_mode')
const setPerGameSettingsEnabled = callable<[string, boolean], PluginSettings>('set_per_game_settings_enabled')
const setButtonPromptFixEnabled = callable<[string, boolean], PluginSettings>('set_button_prompt_fix_enabled')
const setPerGameTrackpadMode = callable<[string, TrackpadMode], PluginSettings>('set_per_game_trackpad_mode')
const setPerGameRumbleEnabled = callable<[string, boolean], PluginSettings>('set_per_game_rumble_enabled')
const setPerGameRumbleIntensity = callable<[string, number], PluginSettings>('set_per_game_rumble_intensity')
const syncPerGameTarget = callable<[string], boolean>('sync_per_game_target')
const setRumbleEnabled = callable<[boolean], PluginSettings>('set_rumble_enabled')
const setRumbleIntensity = callable<[number], PluginSettings>('set_rumble_intensity')
const testRumble = callable<[], boolean>('test_rumble')

type RumbleSaveTarget = { scope: 'global' } | { scope: 'per_game'; appId: string }

const DEFAULT_APP_ID = '0'
const CONTROLLER_STATUS_FAILED_NOTICE = 'Controller failed to initialize. Restart device.'
const CONTROLLER_ACTION_FAILED_NOTICE = "Couldn't update setting."
const CONTROLLER_MODE_ACTION_FAILED_NOTICE = "Couldn't update mode."
const PER_GAME_SETTINGS_ACTION_FAILED_NOTICE = "Couldn't update per-game setting."
const BUTTON_PROMPT_FIX_ACTION_FAILED_NOTICE = "Couldn't update prompt fix."
const TRACKPADS_ACTION_FAILED_NOTICE = "Couldn't update trackpad setting."
const RUMBLE_ACTION_FAILED_NOTICE = "Couldn't update vibration."
const RUMBLE_TEST_FAILED_NOTICE = "Couldn't send vibration test."

function getControllerStatusNotice(status: PluginStatus) {
  if (status.state === 'unsupported') {
    return status.message
  }

  if (status.state === 'failed') {
    return CONTROLLER_STATUS_FAILED_NOTICE
  }

  return null
}

function isControllerModeConfirmed(settings: PluginSettings) {
  return settings.controllerModeAvailable && settings.controllerMode === 'gamepad'
}

async function syncActiveGameTarget(appId: string) {
  try {
    await syncPerGameTarget(appId)
  } catch (error) {
    console.error('Failed to sync per-game target', error)
  }
}

function areRumbleSaveTargetsEqual(left: RumbleSaveTarget, right: RumbleSaveTarget) {
  if (left.scope !== right.scope) {
    return false
  }

  if (left.scope === 'global' || right.scope === 'global') {
    return true
  }

  return left.appId === right.appId
}

const ControllerPanel = ({ activeGame, settings, status, onSettingsChange, onStatusChange }: Props) => {
  const [rumbleIntensityDraft, setRumbleIntensityDraft] = useState(settings.rumbleIntensity)
  const [controllerNotice, setControllerNotice] = useState<string | null>(null)
  const [perGameNotice, setPerGameNotice] = useState<string | null>(null)
  const [savingStartup, setSavingStartup] = useState(false)
  const [savingControllerMode, setSavingControllerMode] = useState(false)
  const [savingHomeButton, setSavingHomeButton] = useState(false)
  const [savingBrightnessDialFix, setSavingBrightnessDialFix] = useState(false)
  const [savingTrackpads, setSavingTrackpads] = useState(false)
  const [savingPerGameSettings, setSavingPerGameSettings] = useState(false)
  const [savingButtonPromptFix, setSavingButtonPromptFix] = useState(false)
  const [savingRumble, setSavingRumble] = useState(false)
  const [savingRumbleIntensity, setSavingRumbleIntensity] = useState(false)
  const [testingRumble, setTestingRumble] = useState(false)
  const [rumbleMessage, setRumbleMessage] = useState<string | null>(null)
  const [rumbleMessageKind, setRumbleMessageKind] = useState<'success' | 'error' | null>(null)
  const rumbleIntensityLatestValue = useRef(settings.rumbleIntensity)
  const rumbleIntensityCommittedValue = useRef(settings.rumbleIntensity)
  const rumbleIntensityLatestTarget = useRef<RumbleSaveTarget>({ scope: 'global' })
  const rumbleIntensitySaveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const rumbleIntensityStateVersion = useRef(0)
  const rumbleIntensityQueuedVersion = useRef<number | null>(null)
  const rumbleIntensityQueuedPromise = useRef<Promise<boolean> | null>(null)
  const rumbleIntensitySaveChain = useRef<Promise<boolean>>(Promise.resolve(true))
  const rumbleIntensityActiveSaveCount = useRef(0)

  const clearPendingRumbleIntensitySave = () => {
    if (rumbleIntensitySaveTimeout.current !== null) {
      clearTimeout(rumbleIntensitySaveTimeout.current)
      rumbleIntensitySaveTimeout.current = null
    }
  }

  const loadStatus = async () => {
    const nextStatus = await getStatus()
    onStatusChange(nextStatus)
  }

  const activeGamePerGameSettings = activeGame ? settings.perGameSettings[activeGame.appid] : undefined
  const isPerGameSettingsEnabled = activeGamePerGameSettings?.enabled ?? false
  const isEditingPerGameOverride = Boolean(activeGame && isPerGameSettingsEnabled)
  const isButtonPromptFixEnabled = activeGamePerGameSettings?.buttonPromptFixEnabled ?? false
  const activeTrackpadMode = isEditingPerGameOverride
    ? activeGamePerGameSettings?.trackpadMode ?? settings.trackpadMode
    : settings.trackpadMode
  const activeRumbleEnabled = isEditingPerGameOverride
    ? activeGamePerGameSettings?.rumbleEnabled ?? settings.rumbleEnabled
    : settings.rumbleEnabled
  const activeRumbleIntensity = isEditingPerGameOverride
    ? activeGamePerGameSettings?.rumbleIntensity ?? settings.rumbleIntensity
    : settings.rumbleIntensity
  const activeRumbleSaveTarget: RumbleSaveTarget =
    isEditingPerGameOverride && activeGame
      ? { scope: 'per_game', appId: activeGame.appid }
      : { scope: 'global' }
  const activeRumbleSaveTargetKey =
    activeRumbleSaveTarget.scope === 'global'
      ? 'global'
      : `per_game:${activeRumbleSaveTarget.appId}`

  const controllerStatusNotice = getControllerStatusNotice(status)

  useDeckyToastNotice(
    controllerStatusNotice
      ? {
          activeKey: `controller-status:${status.state}:${status.message}`,
          title: 'Controller',
          body: controllerStatusNotice,
          severity: 'warning',
        }
      : null,
  )

  useDeckyToastNotice(
    controllerNotice
      ? {
          activeKey: `controller-action:${controllerNotice}`,
          title: 'Controller',
          body: controllerNotice,
          severity: 'error',
        }
      : null,
  )

  useDeckyToastNotice(
    perGameNotice
      ? {
          activeKey: `controller-per-game:${perGameNotice}`,
          title: 'Controller',
          body: perGameNotice,
          severity: 'error',
        }
      : null,
  )

  useDeckyToastNotice(
    rumbleMessage && rumbleMessageKind === 'error'
      ? {
          activeKey: `controller-rumble:error:${rumbleMessage}`,
          title: 'Controller',
          body: rumbleMessage,
          severity: 'error',
        }
      : null,
  )

  useEffect(() => {
    setRumbleIntensityDraft(activeRumbleIntensity)
    rumbleIntensityLatestValue.current = activeRumbleIntensity
    rumbleIntensityCommittedValue.current = activeRumbleIntensity
    rumbleIntensityLatestTarget.current = activeRumbleSaveTarget
    if (!settings.rumbleAvailable) {
      setRumbleMessage(null)
      setRumbleMessageKind(null)
    }
  }, [
    activeRumbleIntensity,
    activeRumbleSaveTargetKey,
    settings.rumbleAvailable,
  ])

  useEffect(() => {
    return () => {
      clearPendingRumbleIntensitySave()
    }
  }, [])

  const handleStartupToggleChange = async (enabled: boolean) => {
    setControllerNotice(null)
    setSavingStartup(true)
    try {
      const nextSettings = await setStartupApplyEnabled(enabled)
      onSettingsChange(nextSettings)
      setControllerNotice(null)
      await loadStatus()
      await syncActiveGameTarget(activeGame?.appid ?? DEFAULT_APP_ID)
    } catch {
      setControllerNotice(CONTROLLER_ACTION_FAILED_NOTICE)
    } finally {
      setSavingStartup(false)
    }
  }

  const handleHomeButtonToggleChange = async (enabled: boolean) => {
    setControllerNotice(null)
    setSavingHomeButton(true)
    try {
      const nextSettings = await setHomeButtonEnabled(enabled)
      onSettingsChange(nextSettings)
      setControllerNotice(null)
    } catch {
      setControllerNotice(CONTROLLER_ACTION_FAILED_NOTICE)
    } finally {
      setSavingHomeButton(false)
    }
  }

  const handleControllerModeChange = async (mode: ControllerMode) => {
    setControllerNotice(null)
    setSavingControllerMode(true)
    try {
      const nextSettings = await setControllerMode(mode)
      onSettingsChange(nextSettings)
      setControllerNotice(null)
      await loadStatus()
      await syncActiveGameTarget(activeGame?.appid ?? DEFAULT_APP_ID)
    } catch {
      setControllerNotice(CONTROLLER_MODE_ACTION_FAILED_NOTICE)
    } finally {
      setSavingControllerMode(false)
    }
  }

  const handleBrightnessDialFixToggleChange = async (enabled: boolean) => {
    setControllerNotice(null)
    setSavingBrightnessDialFix(true)
    try {
      const nextSettings = await setBrightnessDialFixEnabled(enabled)
      onSettingsChange(nextSettings)
      setControllerNotice(null)
    } catch {
      setControllerNotice(CONTROLLER_ACTION_FAILED_NOTICE)
    } finally {
      setSavingBrightnessDialFix(false)
    }
  }

  const handleTrackpadModeChange = async (mode: TrackpadMode) => {
    const appId = activeGame?.appid ?? DEFAULT_APP_ID
    const previousSettings = settings
    let optimisticSettings: PluginSettings | null = null

    if (isEditingPerGameOverride && activeGame) {
      const existingEntry = settings.perGameSettings[activeGame.appid] ?? {
        enabled: true,
        buttonPromptFixEnabled: false,
        trackpadMode: settings.trackpadMode,
        rumbleEnabled: settings.rumbleEnabled,
        rumbleIntensity: settings.rumbleIntensity,
        m1RemapTarget: 'none',
        m2RemapTarget: 'none',
      }
      optimisticSettings = {
        ...settings,
        perGameSettings: {
          ...settings.perGameSettings,
          [activeGame.appid]: {
            ...existingEntry,
            trackpadMode: mode,
          },
        },
      }
    } else {
      optimisticSettings = {
        ...settings,
        trackpadMode: mode,
      }
    }

    setControllerNotice(null)
    setPerGameNotice(null)
    setSavingTrackpads(true)
    onSettingsChange(optimisticSettings)
    try {
      const nextSettings = isEditingPerGameOverride && activeGame
        ? await setPerGameTrackpadMode(activeGame.appid, mode)
        : await setTrackpadMode(mode)
      onSettingsChange(nextSettings)
      setControllerNotice(null)
      setPerGameNotice(null)
      await syncActiveGameTarget(appId)
    } catch {
      onSettingsChange(previousSettings)
      if (isEditingPerGameOverride && activeGame) {
        setPerGameNotice(TRACKPADS_ACTION_FAILED_NOTICE)
      } else {
        setControllerNotice(TRACKPADS_ACTION_FAILED_NOTICE)
      }
    } finally {
      setSavingTrackpads(false)
    }
  }

  const handlePerGameSettingsToggleChange = async (enabled: boolean) => {
    if (!activeGame) {
      return
    }

    setPerGameNotice(null)
    setSavingPerGameSettings(true)
    try {
      const nextSettings = await setPerGameSettingsEnabled(activeGame.appid, enabled)
      onSettingsChange(nextSettings)
      setPerGameNotice(null)
      await syncActiveGameTarget(activeGame.appid)
    } catch {
      setPerGameNotice(PER_GAME_SETTINGS_ACTION_FAILED_NOTICE)
    } finally {
      setSavingPerGameSettings(false)
    }
  }

  const handleButtonPromptFixToggleChange = async (enabled: boolean) => {
    if (!activeGame) {
      return
    }

    setPerGameNotice(null)
    setSavingButtonPromptFix(true)
    try {
      const nextSettings = await setButtonPromptFixEnabled(activeGame.appid, enabled)
      onSettingsChange(nextSettings)
      setPerGameNotice(null)
      await syncActiveGameTarget(activeGame.appid)
    } catch {
      setPerGameNotice(BUTTON_PROMPT_FIX_ACTION_FAILED_NOTICE)
    } finally {
      setSavingButtonPromptFix(false)
    }
  }

  const handleRumbleToggleChange = async (enabled: boolean) => {
    rumbleIntensityStateVersion.current += 1
    clearPendingRumbleIntensitySave()

    setRumbleMessage(null)
    setRumbleMessageKind(null)
    setSavingRumble(true)
    try {
      const nextSettings = isEditingPerGameOverride && activeGame
        ? await setPerGameRumbleEnabled(activeGame.appid, enabled)
        : await setRumbleEnabled(enabled)
      onSettingsChange(nextSettings)
      setRumbleMessage(null)
      setRumbleMessageKind(null)
    } catch {
      setRumbleMessage(RUMBLE_ACTION_FAILED_NOTICE)
      setRumbleMessageKind('error')
    } finally {
      setSavingRumble(false)
    }
  }

  const beginRumbleIntensitySave = () => {
    rumbleIntensityActiveSaveCount.current += 1
    setSavingRumbleIntensity(true)
  }

  const finishRumbleIntensitySave = () => {
    rumbleIntensityActiveSaveCount.current = Math.max(0, rumbleIntensityActiveSaveCount.current - 1)
    if (rumbleIntensityActiveSaveCount.current === 0) {
      setSavingRumbleIntensity(false)
    }
  }

  const saveRumbleIntensity = async (value: number, version: number, target: RumbleSaveTarget) => {
    beginRumbleIntensitySave()
    try {
      const nextSettings =
        target.scope === 'per_game'
          ? await setPerGameRumbleIntensity(target.appId, value)
          : await setRumbleIntensity(value)
      if (
        version === rumbleIntensityStateVersion.current &&
        areRumbleSaveTargetsEqual(target, rumbleIntensityLatestTarget.current)
      ) {
        rumbleIntensityCommittedValue.current = value
        rumbleIntensityLatestValue.current = value
        setRumbleIntensityDraft(value)
        onSettingsChange(nextSettings)
        setRumbleMessage(null)
        setRumbleMessageKind(null)
      } else {
        onSettingsChange(nextSettings)
      }
      return true
    } catch {
      if (
        version === rumbleIntensityStateVersion.current &&
        areRumbleSaveTargetsEqual(target, rumbleIntensityLatestTarget.current)
      ) {
        setRumbleMessage(RUMBLE_ACTION_FAILED_NOTICE)
        setRumbleMessageKind('error')
      }
      return false
    } finally {
      finishRumbleIntensitySave()
    }
  }

  const queueRumbleIntensitySave = (value: number, version: number, target: RumbleSaveTarget) => {
    if (rumbleIntensityQueuedVersion.current === version && rumbleIntensityQueuedPromise.current) {
      return rumbleIntensityQueuedPromise.current
    }

    const nextSave = rumbleIntensitySaveChain.current
      .catch(() => false)
      .then(() => saveRumbleIntensity(value, version, target))

    const trackedSave = nextSave.finally(() => {
      if (rumbleIntensityQueuedVersion.current === version) {
        rumbleIntensityQueuedVersion.current = null
        rumbleIntensityQueuedPromise.current = null
      }
    })

    rumbleIntensitySaveChain.current = trackedSave
    rumbleIntensityQueuedVersion.current = version
    rumbleIntensityQueuedPromise.current = trackedSave
    return trackedSave
  }

  const flushPendingRumbleIntensitySave = async () => {
    clearPendingRumbleIntensitySave()

    const latestValue = rumbleIntensityLatestValue.current
    const latestVersion = rumbleIntensityStateVersion.current
    const latestTarget = rumbleIntensityLatestTarget.current

    if (latestValue === rumbleIntensityCommittedValue.current && !savingRumbleIntensity) {
      return true
    }

    return await queueRumbleIntensitySave(latestValue, latestVersion, latestTarget)
  }

  const handleRumbleIntensityChange = (value: number) => {
    const nextVersion = rumbleIntensityStateVersion.current + 1
    rumbleIntensityStateVersion.current = nextVersion
    setRumbleIntensityDraft(value)
    rumbleIntensityLatestValue.current = value
    rumbleIntensityLatestTarget.current = activeRumbleSaveTarget
    setRumbleMessage(null)
    setRumbleMessageKind(null)
    clearPendingRumbleIntensitySave()
    rumbleIntensitySaveTimeout.current = setTimeout(() => {
      rumbleIntensitySaveTimeout.current = null
      void queueRumbleIntensitySave(value, nextVersion, activeRumbleSaveTarget)
    }, 500)
  }

  const handleTestRumble = async () => {
    setRumbleMessage(null)
    setRumbleMessageKind(null)

    const didFlushIntensity = await flushPendingRumbleIntensitySave()
    if (!didFlushIntensity) {
      return
    }

    setTestingRumble(true)
    try {
      const success = await testRumble()
      if (!success) {
        setRumbleMessage(RUMBLE_TEST_FAILED_NOTICE)
        setRumbleMessageKind('error')
      }
    } catch {
      setRumbleMessage(RUMBLE_TEST_FAILED_NOTICE)
      setRumbleMessageKind('error')
    } finally {
      setTestingRumble(false)
    }
  }

  const controllerModeBlocked = !isControllerModeConfirmed(settings)

  const controllerSpinner = savingControllerMode || savingRumbleIntensity

  return (
    <PanelSection title="Controller" spinner={controllerSpinner}>
      <ControllerTogglesPanel
        settings={settings}
        savingStartup={savingStartup}
        savingControllerMode={savingControllerMode}
        savingHomeButton={savingHomeButton}
        savingBrightnessDialFix={savingBrightnessDialFix}
        onStartupToggleChange={(value: boolean) => void handleStartupToggleChange(value)}
        onControllerModeChange={(value: ControllerMode) => void handleControllerModeChange(value)}
        onHomeButtonToggleChange={(value: boolean) => void handleHomeButtonToggleChange(value)}
        onBrightnessDialFixToggleChange={(value: boolean) => void handleBrightnessDialFixToggleChange(value)}
      />
      <PerGameSettingsPanel
        activeGame={activeGame}
        inputplumberAvailable={settings.inputplumberAvailable}
        isPerGameSettingsEnabled={isPerGameSettingsEnabled}
        isButtonPromptFixEnabled={isButtonPromptFixEnabled}
        savingPerGameSettings={savingPerGameSettings}
        savingButtonPromptFix={savingButtonPromptFix}
        onPerGameSettingsToggleChange={(value: boolean) => void handlePerGameSettingsToggleChange(value)}
        onButtonPromptFixToggleChange={(value: boolean) => void handleButtonPromptFixToggleChange(value)}
      />
      <RumblePanel
        inputplumberAvailable={settings.inputplumberAvailable}
        rumbleEnabled={activeRumbleEnabled}
        rumbleAvailable={settings.rumbleAvailable}
        savingRumble={savingRumble}
        savingRumbleIntensity={savingRumbleIntensity}
        testingRumble={testingRumble}
        rumbleIntensityDraft={rumbleIntensityDraft}
        onRumbleToggleChange={(value: boolean) => void handleRumbleToggleChange(value)}
        onRumbleIntensityChange={handleRumbleIntensityChange}
        onTestRumble={() => void handleTestRumble()}
      />
      <TrackpadPanel
        inputplumberAvailable={settings.inputplumberAvailable}
        controllerModeBlocked={controllerModeBlocked}
        savingTrackpads={savingTrackpads}
        trackpadMode={activeTrackpadMode}
        onTrackpadModeChange={(value: TrackpadMode) => void handleTrackpadModeChange(value)}
      />
    </PanelSection>
  )
}

export default ControllerPanel
