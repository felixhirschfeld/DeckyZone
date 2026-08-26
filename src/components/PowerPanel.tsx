import { callable } from '@decky/api'
import { ButtonItem, Field, PanelSection, PanelSectionRow, ToggleField } from '@decky/ui'
import { useState } from 'react'
import type { PluginSettings } from '../types/plugin'
import { useDeckyToastNotice } from '../utils/toasts'

type Props = {
  settings: PluginSettings
  onSettingsChange: (nextSettings: PluginSettings) => void
}

const setFixSleepEnabled = callable<[boolean], PluginSettings>('set_fix_sleep_enabled')

function getIommuStatus(settings: PluginSettings) {
  const { sleepFix } = settings
  if (!sleepFix.available) {
    return 'Unavailable'
  }
  if (sleepFix.status === 'configuration_drift') {
    return 'Configuration needs repair'
  }
  if (sleepFix.status === 'pending_reboot') {
    return 'Pending restart'
  }
  if (sleepFix.runtimeIommuDisabled === false) {
    return 'Not disabled for this boot'
  }
  if (sleepFix.runtimeIommuDisabled === true) {
    return 'Disabled for this boot'
  }
  return 'Unknown'
}

const PowerPanel = ({ settings, onSettingsChange }: Props) => {
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState<{ body: string; severity: 'error' | 'success' } | null>(null)
  const { sleepFix } = settings

  useDeckyToastNotice(
    notice
      ? {
          activeKey: `${notice.severity}:${notice.body}`,
          title: 'Fix Sleep',
          ...notice,
        }
      : null,
  )

  const applyFixSleep = async (enabled: boolean) => {
    setSaving(true)
    setNotice(null)
    try {
      const nextSettings = await setFixSleepEnabled(enabled)
      onSettingsChange(nextSettings)
      setNotice({
        body: enabled ? 'Restart required to apply the AMD IOMMU change.' : 'Restart required to restore the AMD IOMMU setting.',
        severity: 'success',
      })
    } catch (error) {
      const message = error instanceof Error && error.message ? error.message : "Couldn't update Fix Sleep."
      setNotice({ body: message, severity: 'error' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <PanelSection title="Power">
      <PanelSectionRow>
        <ToggleField
          label="Fix Sleep"
          checked={sleepFix.enabled}
          onChange={(value: boolean) => void applyFixSleep(value)}
          disabled={saving || !sleepFix.available}
          description="Enables AMD IOMMU to improve deep sleep on ZOTAC ZONE. Restart required."
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <Field focusable disabled label="AMD IOMMU" description={sleepFix.message}>
          {getIommuStatus(settings)}
        </Field>
      </PanelSectionRow>
      {sleepFix.enabled && sleepFix.status === 'configuration_drift' && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => void applyFixSleep(true)} disabled={saving}>
            Reapply Fix
          </ButtonItem>
        </PanelSectionRow>
      )}
    </PanelSection>
  )
}

export default PowerPanel
