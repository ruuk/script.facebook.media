from default import newGraph, FacebookUser
import xbmcaddon #@UnresolvedImport

__addon__ = xbmcaddon.Addon(id='script.facebook.media')


def getCurrentUser():
	uid = __addon__.getSetting('current_user')
	if not uid:
		ulist = getUserList()
		if ulist:
			uid = ulist[0]
	if not uid: return None
	return FacebookUser(uid)

def getUserList():
	ustring = __addon__.getSetting('user_list')
	if not ustring: return []
	return ustring.split(',')
	
def doShareSocial(share):
	user = getCurrentUser()
	if not user: return
	graph = newGraph(	user.email,
						user.password,
						user.id,
						user.token)
	
	if share.shareType == 'imagelink':
		attachement = {	"name": share.title,
						"link": share.link,
						"caption": share.title,
						"description": "Shared From XBMC",
						"picture": share.thumbnail}
		
		graph.putWallPost(share.title, attachment=attachement)
	else:
		return False
	return True