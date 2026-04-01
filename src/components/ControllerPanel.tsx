import { callable } from '@decky/api'
import { PanelSection, PanelSectionRow, gamepadDialogClasses } from '@decky/ui'
import { useEffect, useRef, useState } from 'react'
import ControllerTogglesPanel from './controller/ControllerTogglesPanel'
import PerGameSettingsPanel from './controller/PerGameSettingsPanel'
import RumblePanel from './controller/RumblePanel'
import type { ActiveGame, PluginSettings, PluginStatus } from '../types/plugin'

type SteamInputDiagnosticAppDetails = {
  bShowControllerConfig?: boolean
  eEnableThirdPartyControllerConfiguration?: number
  eSteamInputControllerMask?: number
}

type SteamInputDiagnosticState =
  | { state: 'idle' }
  | { state: 'loading'; appId: string }
  | { state: 'ready'; appId: string; details: SteamInputDiagnosticAppDetails }
  | { state: 'unavailable'; appId: string; message: string }

type SteamAppsClient = {
  GetCachedAppDetails?: (appId: number) => Promise<unknown>
  RegisterForAppDetails?: (appId: number, callback: (details: unknown) => void) => { unregister?: () => void }
}

type Props = {
  activeGame: ActiveGame | null
  settings: PluginSettings
  status: PluginStatus
  onSettingsChange: (nextSettings: PluginSettings) => void
  onStatusChange: (nextStatus: PluginStatus) => void
}

const getStatus = callable<[], PluginStatus>('get_status')
const setStartupApplyEnabled = callable<[boolean], PluginSettings>('set_startup_apply_enabled')
const setHomeButtonEnabled = callable<[boolean], PluginSettings>('set_home_button_enabled')
const setBrightnessDialFixEnabled = callable<[boolean], PluginSettings>('set_brightness_dial_fix_enabled')
const setPerGameSettingsEnabled = callable<[string, boolean], PluginSettings>('set_per_game_settings_enabled')
const setButtonPromptFixEnabled = callable<[string, boolean], PluginSettings>('set_button_prompt_fix_enabled')
const setPerGameTrackpadsDisabled = callable<[string, boolean], PluginSettings>('set_per_game_trackpads_disabled')
const syncPerGameTarget = callable<[string], boolean>('sync_per_game_target')
const setRumbleEnabled = callable<[boolean], PluginSettings>('set_rumble_enabled')
const setRumbleIntensity = callable<[number], PluginSettings>('set_rumble_intensity')
const testRumble = callable<[], boolean>('test_rumble')

const DEFAULT_APP_ID = '0'
const STEAM_INPUT_DIAGNOSTIC_UNAVAILABLE_MESSAGE = 'Steam Input state unavailable.'
const SUPPORT_POPUP_HINT = 'Open the header info popup for details.'
const CONTROLLER_STATUS_FAILED_NOTICE = `Controller setup needs attention. ${SUPPORT_POPUP_HINT}`
const CONTROLLER_ACTION_FAILED_NOTICE = `Couldn't update the controller setting. ${SUPPORT_POPUP_HINT}`
const PER_GAME_SETTINGS_ACTION_FAILED_NOTICE = `Couldn't update the per-game setting. ${SUPPORT_POPUP_HINT}`
const BUTTON_PROMPT_FIX_ACTION_FAILED_NOTICE = `Couldn't update the button prompt fix. ${SUPPORT_POPUP_HINT}`
const TRACKPADS_ACTION_FAILED_NOTICE = `Couldn't update the trackpad setting. ${SUPPORT_POPUP_HINT}`
const RUMBLE_ACTION_FAILED_NOTICE = `Couldn't update vibration. ${SUPPORT_POPUP_HINT}`
const RUMBLE_TEST_FAILED_NOTICE = `Couldn't send a vibration test. ${SUPPORT_POPUP_HINT}`

function getControllerStatusNotice(status: PluginStatus) {
  if (status.state === 'unsupported') {
    return status.message
  }

  if (status.state === 'failed') {
    return CONTROLLER_STATUS_FAILED_NOTICE
  }

  return null
}

function normalizeSteamInputDiagnosticDetails(rawDetails: unknown): SteamInputDiagnosticAppDetails | null {
  let parsedDetails = rawDetails

  if (typeof parsedDetails === 'string') {
    try {
      parsedDetails = JSON.parse(parsedDetails)
    } catch {
      return null
    }
  }

  if (!parsedDetails || typeof parsedDetails !== 'object') {
    return null
  }

  const details = parsedDetails as Record<string, unknown>
  const thirdPartyControllerConfiguration = details.eEnableThirdPartyControllerConfiguration
  const steamInputControllerMask = details.eSteamInputControllerMask
  const showControllerConfig = details.bShowControllerConfig

  if (
    typeof thirdPartyControllerConfiguration !== 'number' &&
    typeof steamInputControllerMask !== 'number' &&
    typeof showControllerConfig !== 'boolean'
  ) {
    return null
  }

  return {
    bShowControllerConfig: typeof showControllerConfig === 'boolean' ? showControllerConfig : undefined,
    eEnableThirdPartyControllerConfiguration:
      typeof thirdPartyControllerConfiguration === 'number' ? thirdPartyControllerConfiguration : undefined,
    eSteamInputControllerMask: typeof steamInputControllerMask === 'number' ? steamInputControllerMask : undefined,
  }
}

function getSteamInputDiagnosticStatus(details: SteamInputDiagnosticAppDetails) {
  switch (details.eEnableThirdPartyControllerConfiguration) {
    case 0:
      return details.bShowControllerConfig === false ? 'Steam Input disabled' : 'Mixed or unknown Steam Input state'
    case 1:
      return details.bShowControllerConfig === true ? 'Steam Input enabled/default' : 'Mixed or unknown Steam Input state'
    case 2:
      return 'Steam Input enabled/forced'
    default:
      return 'Mixed or unknown Steam Input state'
  }
}

async function syncActiveGameTarget(appId: string) {
  try {
    await syncPerGameTarget(appId)
  } catch (error) {
    console.error('Failed to sync per-game target', error)
  }
}

const ControllerPanel = ({ activeGame, settings, status, onSettingsChange, onStatusChange }: Props) => {
  const [rumbleIntensityDraft, setRumbleIntensityDraft] = useState(settings.rumbleIntensity)
  const [controllerNotice, setControllerNotice] = useState<string | null>(null)
  const [perGameNotice, setPerGameNotice] = useState<string | null>(null)
  const [savingStartup, setSavingStartup] = useState(false)
  const [savingHomeButton, setSavingHomeButton] = useState(false)
  const [savingBrightnessDialFix, setSavingBrightnessDialFix] = useState(false)
  const [savingPerGameSettings, setSavingPerGameSettings] = useState(false)
  const [savingButtonPromptFix, setSavingButtonPromptFix] = useState(false)
  const [savingPerGameTrackpads, setSavingPerGameTrackpads] = useState(false)
  const [savingRumble, setSavingRumble] = useState(false)
  const [testingRumble, setTestingRumble] = useState(false)
  const [rumbleMessage, setRumbleMessage] = useState<string | null>(null)
  const [rumbleMessageKind, setRumbleMessageKind] = useState<'success' | 'error' | null>(null)
  const [steamInputDiagnostic, setSteamInputDiagnostic] = useState<SteamInputDiagnosticState>({ state: 'idle' })
  const rumbleIntensityLatestValue = useRef(settings.rumbleIntensity)
  const rumbleIntensitySaveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

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

  useEffect(() => {
    setRumbleIntensityDraft(settings.rumbleIntensity)
    rumbleIntensityLatestValue.current = settings.rumbleIntensity
    if (!settings.rumbleAvailable) {
      setRumbleMessage(null)
      setRumbleMessageKind(null)
    }
  }, [settings.rumbleIntensity, settings.rumbleAvailable])

  useEffect(() => {
    return () => {
      clearPendingRumbleIntensitySave()
    }
  }, [])

  const handleStartupToggleChange = async (enabled: boolean) => {
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

  const handleBrightnessDialFixToggleChange = async (enabled: boolean) => {
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

  const handlePerGameSettingsToggleChange = async (enabled: boolean) => {
    if (!activeGame) {
      return
    }

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

  const handlePerGameTrackpadsChange = async (disabled: boolean) => {
    if (!activeGame || !isPerGameSettingsEnabled || !isButtonPromptFixEnabled) {
      return
    }

    setSavingPerGameTrackpads(true)
    try {
      const nextSettings = await setPerGameTrackpadsDisabled(activeGame.appid, disabled)
      onSettingsChange(nextSettings)
      setPerGameNotice(null)
      await syncActiveGameTarget(activeGame.appid)
    } catch {
      setPerGameNotice(TRACKPADS_ACTION_FAILED_NOTICE)
    } finally {
      setSavingPerGameTrackpads(false)
    }
  }

  const handleRumbleToggleChange = async (enabled: boolean) => {
    if (!enabled) {
      clearPendingRumbleIntensitySave()
    }

    setSavingRumble(true)
    try {
      const nextSettings = await setRumbleEnabled(enabled)
      onSettingsChange(nextSettings)
      setRumbleIntensityDraft(nextSettings.rumbleIntensity)
      rumbleIntensityLatestValue.current = nextSettings.rumbleIntensity
      setRumbleMessage(null)
      setRumbleMessageKind(null)
    } catch {
      setRumbleMessage(RUMBLE_ACTION_FAILED_NOTICE)
      setRumbleMessageKind('error')
    } finally {
      setSavingRumble(false)
    }
  }

  const saveRumbleIntensity = async (value: number) => {
    try {
      const nextSettings = await setRumbleIntensity(value)
      onSettingsChange({
        ...settings,
        rumbleIntensity: nextSettings.rumbleIntensity,
        rumbleAvailable: nextSettings.rumbleAvailable,
      })
      setRumbleMessage(null)
      setRumbleMessageKind(null)
    } catch {
      setRumbleMessage(RUMBLE_ACTION_FAILED_NOTICE)
      setRumbleMessageKind('error')
    }
  }

  const handleRumbleIntensityChange = (value: number) => {
    setRumbleIntensityDraft(value)
    rumbleIntensityLatestValue.current = value
    clearPendingRumbleIntensitySave()
    rumbleIntensitySaveTimeout.current = setTimeout(() => {
      rumbleIntensitySaveTimeout.current = null
      void saveRumbleIntensity(rumbleIntensityLatestValue.current)
    }, 500)
  }

  const handleTestRumble = async () => {
    clearPendingRumbleIntensitySave()
    setTestingRumble(true)
    setRumbleMessage(null)
    setRumbleMessageKind(null)
    try {
      const success = await testRumble()
      setRumbleMessage(success ? 'Vibration test sent.' : RUMBLE_TEST_FAILED_NOTICE)
      setRumbleMessageKind(success ? 'success' : 'error')
    } catch {
      setRumbleMessage(RUMBLE_TEST_FAILED_NOTICE)
      setRumbleMessageKind('error')
    } finally {
      setTestingRumble(false)
    }
  }

  const activeGamePerGameSettings = activeGame ? settings.perGameSettings[activeGame.appid] : undefined
  const controllerFeaturesEnabled = settings.startupApplyEnabled
  const isPerGameSettingsEnabled = activeGamePerGameSettings?.enabled ?? false
  const isButtonPromptFixEnabled = activeGamePerGameSettings?.buttonPromptFixEnabled ?? false
  const isTrackpadsDisabled = activeGamePerGameSettings?.disableTrackpads ?? true

  useEffect(() => {
    if (!activeGame || !isPerGameSettingsEnabled || !isButtonPromptFixEnabled) {
      setSteamInputDiagnostic({ state: 'idle' })
      return
    }

    const steamApps = window.SteamClient?.Apps as SteamAppsClient | undefined
    const numericAppId = Number(activeGame.appid)

    if (!steamApps?.GetCachedAppDetails || Number.isNaN(numericAppId)) {
      setSteamInputDiagnostic({
        state: 'unavailable',
        appId: activeGame.appid,
        message: STEAM_INPUT_DIAGNOSTIC_UNAVAILABLE_MESSAGE,
      })
      return
    }

    let cancelled = false
    setSteamInputDiagnostic({ state: 'loading', appId: activeGame.appid })

    const updateDiagnosticDetails = (rawDetails: unknown) => {
      if (cancelled) {
        return
      }

      const nextDetails = normalizeSteamInputDiagnosticDetails(rawDetails)
      if (!nextDetails) {
        setSteamInputDiagnostic({
          state: 'unavailable',
          appId: activeGame.appid,
          message: STEAM_INPUT_DIAGNOSTIC_UNAVAILABLE_MESSAGE,
        })
        return
      }

      setSteamInputDiagnostic({
        state: 'ready',
        appId: activeGame.appid,
        details: nextDetails,
      })
    }

    void steamApps
      .GetCachedAppDetails(numericAppId)
      .then((details) => {
        updateDiagnosticDetails(details)
      })
      .catch(() => {
        if (cancelled) {
          return
        }

        setSteamInputDiagnostic({
          state: 'unavailable',
          appId: activeGame.appid,
          message: STEAM_INPUT_DIAGNOSTIC_UNAVAILABLE_MESSAGE,
        })
      })

    const registration = steamApps.RegisterForAppDetails?.(numericAppId, (details) => {
      updateDiagnosticDetails(details)
    })

    return () => {
      cancelled = true
      registration?.unregister?.()
    }
  }, [activeGame, isPerGameSettingsEnabled, isButtonPromptFixEnabled])

  const shouldShowSteamInputDisabledWarning =
    steamInputDiagnostic.state === 'ready' && getSteamInputDiagnosticStatus(steamInputDiagnostic.details) === 'Steam Input disabled'
  const isButtonPromptFixActive = settings.inputplumberAvailable && isPerGameSettingsEnabled && isButtonPromptFixEnabled
  const visibleControllerNotice = getControllerStatusNotice(status) ?? controllerNotice

  return (
    <PanelSection title="Controller">
      <ControllerTogglesPanel
        settings={settings}
        savingStartup={savingStartup}
        savingHomeButton={savingHomeButton}
        savingBrightnessDialFix={savingBrightnessDialFix}
        onStartupToggleChange={(value: boolean) => void handleStartupToggleChange(value)}
        onHomeButtonToggleChange={(value: boolean) => void handleHomeButtonToggleChange(value)}
        onBrightnessDialFixToggleChange={(value: boolean) => void handleBrightnessDialFixToggleChange(value)}
      />
      {visibleControllerNotice && (
        <PanelSectionRow>
          <div className={gamepadDialogClasses.FieldDescription}>{visibleControllerNotice}</div>
        </PanelSectionRow>
      )}
      {controllerFeaturesEnabled && (
        <>
          <RumblePanel
            settings={settings}
            savingRumble={savingRumble}
            testingRumble={testingRumble}
            rumbleIntensityDraft={rumbleIntensityDraft}
            rumbleMessage={rumbleMessage}
            rumbleMessageKind={rumbleMessageKind}
            onRumbleToggleChange={(value: boolean) => void handleRumbleToggleChange(value)}
            onRumbleIntensityChange={handleRumbleIntensityChange}
            onTestRumble={() => void handleTestRumble()}
          />
          <PerGameSettingsPanel
            activeGame={activeGame}
            inputplumberAvailable={settings.inputplumberAvailable}
            isPerGameSettingsEnabled={isPerGameSettingsEnabled}
            isButtonPromptFixEnabled={isButtonPromptFixEnabled}
            isButtonPromptFixActive={isButtonPromptFixActive}
            isTrackpadsDisabled={isTrackpadsDisabled}
            savingPerGameSettings={savingPerGameSettings}
            savingButtonPromptFix={savingButtonPromptFix}
            savingPerGameTrackpads={savingPerGameTrackpads}
            shouldShowSteamInputDisabledWarning={shouldShowSteamInputDisabledWarning}
            onPerGameSettingsToggleChange={(value: boolean) => void handlePerGameSettingsToggleChange(value)}
            onButtonPromptFixToggleChange={(value: boolean) => void handleButtonPromptFixToggleChange(value)}
            onPerGameTrackpadsChange={(value: boolean) => void handlePerGameTrackpadsChange(value)}
          />
          {perGameNotice && (
            <PanelSectionRow>
              <div className={gamepadDialogClasses.FieldDescription}>{perGameNotice}</div>
            </PanelSectionRow>
          )}
        </>
      )}
    </PanelSection>
  )
}

export default ControllerPanel
