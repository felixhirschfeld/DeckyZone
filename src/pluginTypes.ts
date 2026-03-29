export type PluginStatus = {
  state: string
  message: string
}

export type MissingGlyphFixGameSettings = {
  disableTrackpads: boolean
}

export type PluginSettings = {
  startupApplyEnabled: boolean
  homeButtonEnabled: boolean
  brightnessDialFixEnabled: boolean
  gamescopeZotacProfileBuiltIn: boolean
  gamescopeZotacProfileInstalled: boolean
  gamescopeGreenTintFixEnabled: boolean
  gamescopeZotacProfileTargetPath: string
  gamescopeZotacProfileVerificationState: string
  inputplumberAvailable: boolean
  pluginVersionNum?: string
  rumbleEnabled: boolean
  rumbleIntensity: number
  rumbleAvailable: boolean
  missingGlyphFixGames: Record<string, MissingGlyphFixGameSettings>
}
