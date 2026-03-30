import { callable } from '@decky/api'
import { PanelSection } from '@decky/ui'
import { useEffect, useRef, useState } from 'react'
import ControllerTogglesPanel from './controller/ControllerTogglesPanel'
import GlyphFixPanel from './controller/GlyphFixPanel'
import RumblePanel from './controller/RumblePanel'
import type { ActiveGame, PluginSettings, PluginStatus } from '../pluginTypes'

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
const setMissingGlyphFixEnabled = callable<[string, boolean], PluginSettings>('set_missing_glyph_fix_enabled')
const setMissingGlyphFixTrackpadsDisabled = callable<[string, boolean], PluginSettings>('set_missing_glyph_fix_trackpads_disabled')
const syncMissingGlyphFixTarget = callable<[string], boolean>('sync_missing_glyph_fix_target')
const setRumbleEnabled = callable<[boolean], PluginSettings>('set_rumble_enabled')
const setRumbleIntensity = callable<[number], PluginSettings>('set_rumble_intensity')
const testRumble = callable<[], boolean>('test_rumble')

const DEFAULT_APP_ID = '0'
const STEAM_INPUT_DIAGNOSTIC_UNAVAILABLE_MESSAGE = 'Steam Input state unavailable.'

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
    await syncMissingGlyphFixTarget(appId)
  } catch (error) {
    console.error('Failed to sync missing glyph fix target', error)
  }
}

const ControllerPanel = ({ activeGame, settings, status, onSettingsChange, onStatusChange }: Props) => {
  const [rumbleIntensityDraft, setRumbleIntensityDraft] = useState(settings.rumbleIntensity)
  const [savingStartup, setSavingStartup] = useState(false)
  const [savingHomeButton, setSavingHomeButton] = useState(false)
  const [savingBrightnessDialFix, setSavingBrightnessDialFix] = useState(false)
  const [savingMissingGlyphFix, setSavingMissingGlyphFix] = useState(false)
  const [savingMissingGlyphFixTrackpads, setSavingMissingGlyphFixTrackpads] = useState(false)
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
      await loadStatus()
      await syncActiveGameTarget(activeGame?.appid ?? DEFAULT_APP_ID)
    } catch (error) {
      onStatusChange({
        state: 'failed',
        message: `Failed to update startup setting: ${String(error)}`,
      })
    } finally {
      setSavingStartup(false)
    }
  }

  const handleHomeButtonToggleChange = async (enabled: boolean) => {
    setSavingHomeButton(true)
    try {
      const nextSettings = await setHomeButtonEnabled(enabled)
      onSettingsChange(nextSettings)
    } catch (error) {
      onStatusChange({
        state: 'failed',
        message: `Failed to update Home button setting: ${String(error)}`,
      })
    } finally {
      setSavingHomeButton(false)
    }
  }

  const handleBrightnessDialFixToggleChange = async (enabled: boolean) => {
    setSavingBrightnessDialFix(true)
    try {
      const nextSettings = await setBrightnessDialFixEnabled(enabled)
      onSettingsChange(nextSettings)
    } catch (error) {
      onStatusChange({
        state: 'failed',
        message: `Failed to update brightness dial fix: ${String(error)}`,
      })
    } finally {
      setSavingBrightnessDialFix(false)
    }
  }

  const handleMissingGlyphFixToggleChange = async (enabled: boolean) => {
    if (!activeGame) {
      return
    }

    setSavingMissingGlyphFix(true)
    try {
      const nextSettings = await setMissingGlyphFixEnabled(activeGame.appid, enabled)
      onSettingsChange(nextSettings)
      await syncActiveGameTarget(activeGame.appid)
    } catch (error) {
      onStatusChange({
        state: 'failed',
        message: `Failed to update missing glyph fix: ${String(error)}`,
      })
    } finally {
      setSavingMissingGlyphFix(false)
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
      await loadStatus()
    } catch (error) {
      onStatusChange({
        state: 'failed',
        message: `Failed to update rumble setting: ${String(error)}`,
      })
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
    } catch (error) {
      onStatusChange({
        state: 'failed',
        message: `Failed to update vibration intensity: ${String(error)}`,
      })
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
      setRumbleMessage(success ? 'Sent a test rumble event.' : 'Failed to send a test rumble event.')
      setRumbleMessageKind(success ? 'success' : 'error')
    } catch (error) {
      setRumbleMessage(`Failed to send a test rumble event: ${String(error)}`)
      setRumbleMessageKind('error')
    } finally {
      setTestingRumble(false)
    }
  }

  const handleMissingGlyphFixTrackpadsChange = async (disabled: boolean) => {
    if (!activeGame || !isMissingGlyphFixEnabled) {
      return
    }

    setSavingMissingGlyphFixTrackpads(true)
    try {
      const nextSettings = await setMissingGlyphFixTrackpadsDisabled(activeGame.appid, disabled)
      onSettingsChange(nextSettings)
      await syncActiveGameTarget(activeGame.appid)
    } catch (error) {
      onStatusChange({
        state: 'failed',
        message: `Failed to update trackpad setting: ${String(error)}`,
      })
    } finally {
      setSavingMissingGlyphFixTrackpads(false)
    }
  }

  const activeGameGlyphFixSettings = activeGame ? settings.missingGlyphFixGames[activeGame.appid] : undefined
  const isMissingGlyphFixEnabled = Boolean(activeGameGlyphFixSettings)
  const isTrackpadsDisabled = activeGameGlyphFixSettings?.disableTrackpads ?? true

  useEffect(() => {
    if (!activeGame || !isMissingGlyphFixEnabled) {
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
  }, [activeGame, isMissingGlyphFixEnabled])

  const shouldShowSteamInputDisabledWarning =
    steamInputDiagnostic.state === 'ready' && getSteamInputDiagnosticStatus(steamInputDiagnostic.details) === 'Steam Input disabled'
  const isMissingGlyphFixActive = settings.inputplumberAvailable && isMissingGlyphFixEnabled

  return (
    <PanelSection title="Controller">
      <ControllerTogglesPanel
        status={status}
        settings={settings}
        savingStartup={savingStartup}
        savingHomeButton={savingHomeButton}
        savingBrightnessDialFix={savingBrightnessDialFix}
        onStartupToggleChange={(value: boolean) => void handleStartupToggleChange(value)}
        onHomeButtonToggleChange={(value: boolean) => void handleHomeButtonToggleChange(value)}
        onBrightnessDialFixToggleChange={(value: boolean) => void handleBrightnessDialFixToggleChange(value)}
      />
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
      <GlyphFixPanel
        activeGame={activeGame}
        inputplumberAvailable={settings.inputplumberAvailable}
        isMissingGlyphFixEnabled={isMissingGlyphFixEnabled}
        isMissingGlyphFixActive={isMissingGlyphFixActive}
        isTrackpadsDisabled={isTrackpadsDisabled}
        savingMissingGlyphFix={savingMissingGlyphFix}
        savingMissingGlyphFixTrackpads={savingMissingGlyphFixTrackpads}
        shouldShowSteamInputDisabledWarning={shouldShowSteamInputDisabledWarning}
        onMissingGlyphFixToggleChange={(value: boolean) => void handleMissingGlyphFixToggleChange(value)}
        onMissingGlyphFixTrackpadsChange={(value: boolean) => void handleMissingGlyphFixTrackpadsChange(value)}
      />
    </PanelSection>
  )
}

export default ControllerPanel
