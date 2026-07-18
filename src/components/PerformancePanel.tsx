import { callable } from '@decky/api'
import { PanelSection, PanelSectionRow, SliderField, gamepadDialogClasses } from '@decky/ui'
import { useEffect, useState } from 'react'
import type { PluginSettings } from '../types/plugin'
import { useDeckyToastNotice } from '../utils/toasts'

type Props = {
  settings: PluginSettings
  onSettingsChange: (nextSettings: PluginSettings) => void
}

const setVramSizeGb = callable<[number], PluginSettings>('set_vram_size_gb')

const VRAM_DEFAULT_GB = 4
const VRAM_DESCRIPTION = 'Memory reserved for the GPU (UMA framebuffer), reboot after changing this'
const VRAM_UNAVAILABLE_DESCRIPTION = 'VRAM control is not available on this device'
const VRAM_UPDATE_FAILED_NOTICE = "Couldn't update VRAM size."
const VRAM_REBOOT_REQUIRED_NOTICE = 'Reboot to apply VRAM change.'

function clampVramGb(value: number, minVramGb: number, maxVramGb: number) {
  return Math.min(maxVramGb, Math.max(minVramGb, Math.round(value)))
}

function getVramSliderValue(settings: PluginSettings) {
  const { pendingVramGb, activeVramGb, minVramGb, maxVramGb } = settings.vram
  return clampVramGb(pendingVramGb ?? activeVramGb ?? VRAM_DEFAULT_GB, minVramGb, maxVramGb)
}

function getVramDescription(settings: PluginSettings) {
  if (!settings.vram.available) {
    return VRAM_UNAVAILABLE_DESCRIPTION
  }

  return VRAM_DESCRIPTION
}

function getVramRebootHint(settings: PluginSettings) {
  const { available, rebootRequired, pendingVramGb, activeVramGb } = settings.vram
  if (!available || !rebootRequired || pendingVramGb === null || activeVramGb === null) {
    return null
  }

  return `Reboot required: ${activeVramGb} GB active, ${pendingVramGb} GB after reboot`
}

const PerformancePanel = ({ settings, onSettingsChange }: Props) => {
  const [savingVram, setSavingVram] = useState(false)
  const [vramDraftGb, setVramDraftGb] = useState(() => getVramSliderValue(settings))
  const [vramNotice, setVramNotice] = useState<string | null>(null)
  const vramRebootHint = getVramRebootHint(settings)

  useEffect(() => {
    setVramDraftGb(getVramSliderValue(settings))
  }, [settings.vram.pendingVramGb, settings.vram.activeVramGb])

  useDeckyToastNotice(
    vramNotice
      ? {
          activeKey: `vram-action:${vramNotice}:${vramDraftGb}`,
          title: 'Performance',
          body: vramNotice,
          severity: vramNotice === VRAM_UPDATE_FAILED_NOTICE ? 'error' : 'warning',
        }
      : null,
  )

  const handleVramChange = async (nextVramGb: number) => {
    const clampedVramGb = clampVramGb(nextVramGb, settings.vram.minVramGb, settings.vram.maxVramGb)
    if (clampedVramGb === (settings.vram.pendingVramGb ?? null)) {
      setVramDraftGb(clampedVramGb)
      return
    }

    setVramNotice(null)
    setSavingVram(true)
    setVramDraftGb(clampedVramGb)
    try {
      const nextSettings = await setVramSizeGb(clampedVramGb)
      onSettingsChange(nextSettings)
      setVramNotice(
        nextSettings.vram.pendingVramGb !== clampedVramGb ? VRAM_UPDATE_FAILED_NOTICE : VRAM_REBOOT_REQUIRED_NOTICE,
      )
    } catch {
      setVramNotice(VRAM_UPDATE_FAILED_NOTICE)
      setVramDraftGb(getVramSliderValue(settings))
    } finally {
      setSavingVram(false)
    }
  }

  return (
    <PanelSection title="Performance">
      <PanelSectionRow>
        <SliderField
          label="VRAM Size"
          description={getVramDescription(settings)}
          value={vramDraftGb}
          min={settings.vram.minVramGb}
          max={settings.vram.maxVramGb}
          step={1}
          notchCount={settings.vram.maxVramGb - settings.vram.minVramGb + 1}
          notchTicksVisible
          showValue
          valueSuffix=" GB"
          resetValue={VRAM_DEFAULT_GB}
          onChange={(value: number) => void handleVramChange(value)}
          disabled={savingVram || !settings.vram.available}
        />
      </PanelSectionRow>
      {vramRebootHint && (
        <PanelSectionRow>
          <div className={gamepadDialogClasses.FieldDescription}>{vramRebootHint}</div>
        </PanelSectionRow>
      )}
    </PanelSection>
  )
}

export default PerformancePanel
