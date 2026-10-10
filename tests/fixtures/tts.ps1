param([string]$Out, [string]$Text)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Zira Desktop')
$s.Rate = 0
$s.SetOutputToWaveFile($Out)
$s.Speak($Text)
$s.Dispose()
