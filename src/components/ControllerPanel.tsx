import { callable } from '@decky/api'
import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  SliderField,
  ToggleField,
  gamepadDialogClasses,
} from '@decky/ui'
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
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
const DEFAULT_STARTUP_DESCRIPTION = 'Sets the Zotac controller now and after boot. Makes the dials work.'
const HOME_BUTTON_TOGGLE_DESCRIPTION = 'Opens Home.'
const HOME_BUTTON_TOGGLE_DISABLED_DESCRIPTION = 'Opens Home. Enable Controller first.'
const DEFAULT_BRIGHTNESS_DIAL_FIX_DESCRIPTION = 'Uses the right dial for screen brightness.'
const BRIGHTNESS_DIAL_FIX_DISABLED_DESCRIPTION = 'Uses the right dial for screen brightness. Enable Controller first.'
const DEFAULT_RUMBLE_DESCRIPTION = 'Change and test vibration intensity.'
const RUMBLE_UNAVAILABLE_MESSAGE = 'Rumble device is not available.'
const NO_ACTIVE_GAME_GLYPH_FIX_DESCRIPTION = 'Launch a game to enable this fix.'
const DISABLE_TRACKPADS_DESCRIPTION = 'Turns off the trackpads while this fix is on.'
const STEAM_INPUT_DIAGNOSTIC_UNAVAILABLE_MESSAGE = 'Steam Input state unavailable.'

function getStartupDescription(status: PluginStatus, settings: PluginSettings) {
  if (!settings.inputplumberAvailable) {
    return 'InputPlumber is not available.'
  }

  if (status.state === 'failed' || status.state === 'disabled' || status.state === 'unsupported') {
    return status.message
  }

  return DEFAULT_STARTUP_DESCRIPTION
}

function getRumbleDescription(settings: PluginSettings) {
  if (!settings.rumbleAvailable) {
    return RUMBLE_UNAVAILABLE_MESSAGE
  }

  return DEFAULT_RUMBLE_DESCRIPTION
}

function getBrightnessDialFixDescription(settings: PluginSettings) {
  if (!settings.inputplumberAvailable) {
    return 'InputPlumber is not available.'
  }

  if (!settings.startupApplyEnabled) {
    return BRIGHTNESS_DIAL_FIX_DISABLED_DESCRIPTION
  }

  return DEFAULT_BRIGHTNESS_DIAL_FIX_DESCRIPTION
}

function getActiveGameIconSource(activeGame: ActiveGame | null) {
  if (!activeGame) {
    return null
  }

  if (activeGame.icon_data && activeGame.icon_data_format) {
    return `data:image/${activeGame.icon_data_format};base64,${activeGame.icon_data}`
  }

  if (activeGame.icon_hash) {
    return `/assets/${activeGame.appid}/${activeGame.icon_hash}.jpg?c=${activeGame.local_cache_version ?? ''}`
  }

  return null
}

function getMissingGlyphFixDescription(activeGame: ActiveGame | null): ReactNode {
  if (!activeGame) {
    return NO_ACTIVE_GAME_GLYPH_FIX_DESCRIPTION
  }

  const iconSource = getActiveGameIconSource(activeGame)
  const description = `Fixes button prompts and glyphs for ${activeGame.display_name}.`

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      {iconSource ? <img src={iconSource} width={20} height={20} style={{ borderRadius: '4px', flexShrink: 0 }} /> : null}
      <div
        style={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {description}
      </div>
    </div>
  )
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
  const controllerDependentToggleDisabled = !settings.startupApplyEnabled
  const inputplumberDependentControlDisabled = !settings.inputplumberAvailable
  const isMissingGlyphFixActive = settings.inputplumberAvailable && isMissingGlyphFixEnabled

  return (
    <PanelSection title="Controller">
      <PanelSectionRow>
        <ToggleField
          label="Enable Controller"
          checked={settings.startupApplyEnabled}
          onChange={(value: boolean) => void handleStartupToggleChange(value)}
          disabled={savingStartup || !settings.inputplumberAvailable}
          description={getStartupDescription(status, settings)}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label="Enable Home Button"
          checked={settings.homeButtonEnabled}
          onChange={(value: boolean) => void handleHomeButtonToggleChange(value)}
          disabled={savingHomeButton || !settings.startupApplyEnabled || !settings.inputplumberAvailable}
          description={
            inputplumberDependentControlDisabled
              ? 'InputPlumber is not available.'
              : controllerDependentToggleDisabled
                ? HOME_BUTTON_TOGGLE_DISABLED_DESCRIPTION
                : HOME_BUTTON_TOGGLE_DESCRIPTION
          }
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label="Enable Brightness Dial"
          checked={settings.brightnessDialFixEnabled}
          onChange={(value: boolean) => void handleBrightnessDialFixToggleChange(value)}
          disabled={savingBrightnessDialFix || !settings.startupApplyEnabled || !settings.inputplumberAvailable}
          description={getBrightnessDialFixDescription(settings)}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label="Vibration / Rumble"
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
              value={rumbleIntensityDraft}
              min={0}
              max={100}
              step={5}
              notchTicksVisible
              onChange={handleRumbleIntensityChange}
              disabled={savingRumble || !settings.rumbleEnabled || !settings.rumbleAvailable}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={() => void handleTestRumble()}
              disabled={savingRumble || testingRumble || !settings.rumbleEnabled || !settings.rumbleAvailable || !settings.inputplumberAvailable}
            >
              {testingRumble ? 'Testing Rumble...' : `Test  ${rumbleIntensityDraft}% Rumble`}
            </ButtonItem>
          </PanelSectionRow>
          {rumbleMessage && rumbleMessageKind === 'error' && (
            <PanelSectionRow>
              <div
                style={{
                  color: rumbleMessageKind === 'error' ? 'red' : undefined,
                }}
              >
                {rumbleMessage}
              </div>
            </PanelSectionRow>
          )}
        </>
      )}
      <PanelSectionRow>
        <ToggleField
          label="Button Prompt Fix"
          checked={isMissingGlyphFixEnabled}
          onChange={(value: boolean) => void handleMissingGlyphFixToggleChange(value)}
          disabled={!activeGame || savingMissingGlyphFix || !settings.inputplumberAvailable}
          description={settings.inputplumberAvailable ? getMissingGlyphFixDescription(activeGame) : 'InputPlumber is not available.'}
        />
      </PanelSectionRow>
      {activeGame && isMissingGlyphFixActive && shouldShowSteamInputDisabledWarning && (
        <PanelSectionRow>
          <div className={gamepadDialogClasses.FieldDescription}>Steam Input disabled</div>
        </PanelSectionRow>
      )}
      {activeGame && isMissingGlyphFixActive && (
        <PanelSectionRow>
          <ToggleField
            label="Disable Trackpads"
            checked={isTrackpadsDisabled}
            onChange={(value: boolean) => void handleMissingGlyphFixTrackpadsChange(value)}
            disabled={savingMissingGlyphFix || savingMissingGlyphFixTrackpads}
            description={DISABLE_TRACKPADS_DESCRIPTION}
          />
        </PanelSectionRow>
      )}
    </PanelSection>
  )
}

export default ControllerPanel
