import xbmc, xbmcgui

def getpass(prompt='Enter Password:'):
	keyringPass = getKeyringPass()
	if keyringPass: return keyringPass
	key = xbmc.Keyboard('',prompt,True)
	key.doModal()
	if not key.isConfirmed(): return ''
	keyringPass = key.getText()
	saveKeyringPass(keyringPass)
	return keyringPass

def getKeyringPass():
	password = xbmcgui.Window(10000).getProperty('KEYRING_password') or ''
	return password
	
def saveKeyringPass(password):
	xbmcgui.Window(10000).setProperty('KEYRING_password',password)
