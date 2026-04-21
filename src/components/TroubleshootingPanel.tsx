import { callable } from '@decky/api'
import { ButtonItem, ConfirmModal, PanelSection, PanelSectionRow, Spinner, showModal } from '@decky/ui'
import { useState } from 'react'
import { cleanupZotacGlyphsRuntime } from '../glyphs/zotacGlyphRuntime'
import type { PluginResetResult, PluginSettings, PluginStatus } from '../types/plugin'
import { showDeckyToast } from '../utils/toasts'

type Props = {
  onSettingsChange: (nextSettings: PluginSettings) => void
  onStatusChange: (nextStatus: PluginStatus) => void
}

type ResetPluginConfirmModalProps = Props & {
  closeModal?: () => void
}

const resetPlugin = callable<[], PluginResetResult>('reset_plugin')

const RESET_FAILED_NOTICE = 'Reset failed.'
const RESET_COMPLETE_NOTICE = 'Plugin reset complete.'

const titleStyle = {
  display: 'flex',
  flexDirection: 'row' as const,
  alignItems: 'center',
  width: '100%',
}

const spinnerStyle = {
  marginLeft: 'auto',
}

function getPartialResetNotice(result: PluginResetResult, glyphCleanupFailed: boolean) {
  const failedStepCount = result.steps.filter((step) => !step.ok).length
  if (glyphCleanupFailed && failedStepCount > 0) {
    return `${failedStepCount} backend cleanup step${failedStepCount === 1 ? '' : 's'} failed; live glyph cleanup also failed.`
  }

  if (failedStepCount > 0) {
    return `${failedStepCount} backend cleanup step${failedStepCount === 1 ? '' : 's'} failed.`
  }

  return 'Live glyph cleanup failed.'
}

const ResetPluginConfirmModal = ({
  closeModal,
  onSettingsChange,
  onStatusChange,
}: ResetPluginConfirmModalProps) => {
  const [resetting, setResetting] = useState(false)

  const handleReset = async () => {
    setResetting(true)
    let glyphCleanupFailed = false
    let shouldClose = false

    try {
      try {
        await cleanupZotacGlyphsRuntime()
      } catch {
        glyphCleanupFailed = true
      }

      const result = await resetPlugin()
      onSettingsChange(result.settings)
      onStatusChange(result.status)

      if (result.ok && !glyphCleanupFailed) {
        showDeckyToast({
          title: 'Troubleshooting',
          body: RESET_COMPLETE_NOTICE,
          severity: 'success',
        })
      } else {
        showDeckyToast({
          title: 'Troubleshooting',
          body: getPartialResetNotice(result, glyphCleanupFailed),
          severity: 'warning',
        })
      }

      shouldClose = true
    } catch {
      showDeckyToast({
        title: 'Troubleshooting',
        body: RESET_FAILED_NOTICE,
        severity: 'error',
      })
    } finally {
      setResetting(false)
      if (shouldClose) {
        closeModal?.()
      }
    }
  }

  return (
    <ConfirmModal
      closeModal={closeModal}
      onOK={() => void handleReset()}
      bOKDisabled={resetting}
      bCancelDisabled={resetting}
      strTitle={
        <div style={titleStyle}>
          Reset Plugin
          {resetting && <Spinner width="24px" height="24px" style={spinnerStyle} />}
        </div>
      }
      strOKButtonText="Reset"
    >
      Clears DeckyZone settings and removes active runtime changes. The plugin stays installed.
    </ConfirmModal>
  )
}

const TroubleshootingPanel = ({ onSettingsChange, onStatusChange }: Props) => {
  return (
    <PanelSection title="Troubleshooting">
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={() => {
            showModal(
              <ResetPluginConfirmModal
                onSettingsChange={onSettingsChange}
                onStatusChange={onStatusChange}
              />,
            )
          }}
        >
          Reset Plugin
        </ButtonItem>
      </PanelSectionRow>
    </PanelSection>
  )
}

export default TroubleshootingPanel
