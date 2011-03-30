import mc #@UnresolvedImport
import os,binascii,urllib,urllib2,time
import sys, traceback

#import traceback
import facebook
from facebook import GraphAPIError

import locale
loc = locale.getdefaultlocale()
print loc
ENCODING = loc[1] or 'utf-8'

def ENCODE(string):
	return string.encode(ENCODING,'replace')

def LOG(message):
	print 'FACEBOOK MEDIA: %s' % message
	
def ERROR(message):
	LOG(message)
	traceback.print_exc()
	return str(sys.exc_info()[1])
	
class FacebookUser:
	def __init__(self,uid):
		self.id = uid
		config = mc.GetApp().GetLocalConfig()
		self.email = config.GetValue('login_email_%s' % uid)
		self.password = config.GetValue('login_pass_%s' % uid)
		self.token = config.GetValue('token_%s' % uid)
		self.pic = config.GetValue('profile_pic_%s' % uid)
		self.username = config.GetValue('username_%s' % uid)
		
	def updateToken(self,token):
		self.token = token
		mc.GetApp().GetLocalConfig().SetValue('token_%s' % self.id,str(token))

class WindowState:
	def __init__(self):
		self.items = None
		self.listIndex = 0
		self.settings = {}
			
class FacebookSession:
	def __init__(self):
		self.graph = None
		self.states = []
		self.current_state = None
		self.paging = []
		self.lastItemNumber = 0
		self.CACHE_PATH = os.path.join(mc.GetTempDir(),'facebook-media')
		if not os.path.exists(self.CACHE_PATH): os.makedirs(self.CACHE_PATH)
		self.newUserCache = None
		self.currentUser = None
		self.setFriend()
		
		self.imageURLCache = {}
		self.loadImageURLCache()
		
		self.stateSettings = (	'current_friend_name',
								'current_user_pic',
								'current_user_name',
								'last_item_name',
								'current_nav_path')
		self.start()
		
	def start(self):
		user = self.getCurrentUser()
		
		if not user:
			self.openAddUserWindow()
			return
		
		self.graph = self.newGraph(	user.email,
									user.password,
									user.id,
									user.token,
									self.newTokenCallback )
		
		print user.username
		#print user.email
		
		self.loadOptions()
		self.CATEGORIES()
		self.setCurrentState()
		
	def newGraph(self,email,password,uid=None,token=None,new_token_callback=None):
		graph = facebook.GraphWrap(token,new_token_callback=new_token_callback)
		graph.setAppData('150505371652086',scope='user_photos,friends_photos,user_photo_video_tags,friends_photo_video_tags')
		graph.setLogin(email,password,uid)
		return graph
		
	def newTokenCallback(self,token):
		self.token = token
		if self.currentUser: self.currentUser.updateToken(token)
		
	def loadOptions(self):
		items = mc.ListItems()
		for user in self.getUsers():
			item = mc.ListItem( mc.ListItem.MEDIA_UNKNOWN )
			item.SetLabel(user.username)
			item.SetThumbnail(user.pic)
			item.SetProperty('uid',user.id)
			items.append(item)
		options = [	('add_user','facebook-media-icon-adduser.png','Add User','data'),
					('remove_user','facebook-media-icon-removeuser.png','Remove User','data')]
		for action,icon,label,data in options:
			item = mc.ListItem( mc.ListItem.MEDIA_UNKNOWN )
			item.SetThumbnail(icon)
			item.SetLabel(label)
			item.SetProperty('action',action)
			item.SetProperty('data',data)
			items.append(item)
			
		mc.GetWindow(14001).GetList(125).SetItems(items)
		
	def openAddUserWindow(self):
		params = mc.Parameters()
		params['test'] = 'ATEST'
		self.setSetting('auth_step_1','')
		self.setSetting('auth_step_2','')
		self.setSetting('auth_step_3','')
		self.setSetting('auth_step_4','')
		mc.GetApp().ActivateWindow(14002,params)
			
	def saveState(self):
		state = self.createCurrentState()
		self.states.append(state)
		
	def createCurrentState(self,items=None):
		ilist = mc.GetWindow(14001).GetList(120)
		state = WindowState()
		if not items:
			items = ilist.GetItems()
			state.listIndex = ilist.GetFocusedItem()
		state.items = items
		for set in self.stateSettings: state.settings[set] = self.getSetting(set)
		return state
	
	def setCurrentState(self,items=None):
		self.current_state = self.createCurrentState(items)
		
	def popState(self,clear=False):
		if not self.states: return False
		state = self.states.pop()
		if not clear: self.restoreState(state)
		return True
	
	def restoreState(self,state):
		for set in self.stateSettings: self.setSetting(set, '')
		for set in self.stateSettings: self.setSetting(set, state.settings.get(set,''))
		ilist = mc.GetWindow(14001).GetList(120)
		blank = mc.ListItems()
		blank.append(mc.ListItem( mc.ListItem.MEDIA_UNKNOWN ))
		ilist.SetItems(blank)
		self.fillList(state.items)
		ilist.SetFocusedItem(state.listIndex)
			
	def reInitState(self):
		params = mc.Parameters()
		params['none'] = 'NONE'
		mc.GetApp().ActivateWindow(14001,params)
		self.restoreState(self.current_state)
		self.setPathDisplay()

	def getRealURL(self,url):
		if not url: return url
		for ct in range(1,4):
			try:
				req = urllib2.urlopen(url)
				break
			except:
				LOG('getRealURL(): ATTEMPT #%s FAILED' % ct)
		else:
			return url
		return req.geturl()
	
	def setListFocus(self,nextprev,conn_obj):
		ilist = mc.GetWindow(14001).GetList(120)
		if nextprev == 'prev':
			if conn_obj.next: self.jumpToListEnd(ilist,-1)
			else: self.jumpToListEnd(ilist)
		else:
			if conn_obj.previous: ilist.SetFocusedItem(1)
				
	def jumpToListEnd(self,ilist,offset=0):
		idx = len(ilist.GetItems()) - 1
		idx += offset
		if idx < 0: idx = 0
		ilist.SetFocusedItem(idx)
		
	def getPagingItem(self,nextprev,url,itype,current_url=''):
		item = mc.ListItem( mc.ListItem.MEDIA_UNKNOWN )
		item.SetThumbnail('facebook-media-icon-%s.png' % nextprev)
		if nextprev == 'prev': caption = 'PREVIOUS %s' % itype.upper()
		else: caption = 'NEXT %s' % itype.upper()
		if itype == 'albums':
			item.SetLabel(caption)
		else:
			item.SetProperty('caption',caption)
		
		item.SetProperty('category','paging')
		item.SetProperty('paging',ENCODE(url))
		item.SetProperty('nextprev',nextprev)
		item.SetProperty('mediatype',itype)
		item.SetProperty('from_url',current_url)
		item.SetProperty('previous',self.getSetting('last_item_name'))
		return item
		
	def fillList(self,items):
		#Fix for unpredictable Boxee wraplist behavior
		if len(items) < 6:
			newitems = mc.ListItems()
			for y in items: newitems.append(y)
			mult = 6/len(items)
			if mult < 2: mult = 2
			for x in range(1,mult): #@UnusedVariable
				for y in items: newitems.append(y)
			mc.GetWindow(14001).GetList(120).SetItems(newitems)
		else:
			mc.GetWindow(14001).GetList(120).SetItems(items)
		
	def CATEGORIES(self,uid='me',name=''):
		LOG("CATEGORIES - STARTED")
		window = mc.GetWindow(14001)
		if not uid == 'me': self.saveState()
		
		items = mc.ListItems()
		cids = ('albums','videos','friends','photosofme','videosofme')
		if uid == 'me':
			cats = ('ALBUMS','VIDEOS','FRIENDS','PHOTOS OF ME','VIDEOS OF ME')
		else:
			cats = ('ALBUMS','VIDEOS','FRIENDS','PHOTOS OF USER','VIDEOS OF USER')
			
		for cat,cid in zip(cats,cids):
			item = mc.ListItem( mc.ListItem.MEDIA_UNKNOWN )
			#item.SetContentType("")
			item.SetLabel(cat)
			#item.SetDescription(desc)
			item.SetProperty('category',cid)
			item.SetProperty('uid',uid)
			item.SetThumbnail('facebook-media-icon-%s.png' % cid)
			item.SetProperty('background','')
			item.SetProperty('previous',self.getSetting('last_item_name'))
			items.append(item)
		
		mc.HideDialogWait()
		
		self.fillList(items)
		window.GetControl(120).SetFocus()
		self.setCurrentState(items)
		self.setSetting('last_item_name','CATEGORIES')
		LOG("CATEGORIES - STOPPED")

	def ALBUMS(self,item):
		LOG('ALBUMS - STARTED')
		uid = item.GetProperty('uid')
		paging = item.GetProperty('paging')
		nextprev = item.GetProperty('nextprev')
		fromUrl = item.GetProperty('from_url')
		
		if not paging: self.saveState()
		
		self.startProgress('GETTING ALBUMS...')
		
		items = mc.ListItems()
		try:
			self.graph.withProgress(self.updateProgress,0.5,100,'QUERYING FACEBOOK')
			if paging:
				if fromUrl:
					self.paging.append(fromUrl)
				else:
					if self.paging: paging = self.paging.pop()
				albums = self.graph.urlRequest(paging)
			else:
				self.paging = []
				albums = self.graph.getObject(uid).connections.albums()
				
			print albums.next
			print albums.previous
			
			cids = []
			for a in albums:
				cid = a.cover_photo()
				if cid:
					cids.append(cid)
			cover_objects = {}
			if cids: cover_objects = self.graph.getObjects(cids)
			
			if albums.previous:
				item = self.getPagingItem('prev', albums.previous, 'albums')
				items.append(item)	
			
			total = len(albums) or 1
			ct = 0
			offset = 50
			modifier = 50.0 / total
			for a in albums:
				ct += 1
				cover = None
				acp = a.cover_photo()
				if acp: cover = cover_objects[acp]
				if cover:
					tn_url = cover.picture('')
					src_url = cover.source('')
					self.imageURLCache[a.id] = tn_url
				else:
					if a.id in self.imageURLCache:
						tn_url = self.imageURLCache[a.id]
					else:
						tn = "https://graph.facebook.com/"+a.id+"/picture?access_token=" + self.graph.access_token
						tn_url = self.getRealURL(tn)
						self.imageURLCache[a.id] = tn_url
					src_url = tn_url.replace('_a.','_n.')
					
				self.updateProgress(int(ct*modifier)+offset,100,'ALBUM %s OF %s' % (ct,total))

				#aname = a.get('name','').encode('ISO-8859-1','replace')
				aname = ENCODE(a.name(''))
				
				item = mc.ListItem( mc.ListItem.MEDIA_UNKNOWN )
				item.SetLabel(aname)
				item.SetThumbnail(ENCODE(tn_url))
				item.SetImage(0,ENCODE(src_url))
				item.SetProperty('album',ENCODE(a.id))
				item.SetProperty('uid',uid)
				item.SetProperty('category','photos')
				item.SetProperty('previous',self.getSetting('last_item_name'))
				items.append(item)
				
			if albums.next:
				item = self.getPagingItem('next', albums.next, 'albums', paging)
				items.append(item)
				
			self.saveImageURLCache()
		finally:
			self.endProgress()
	
		if items:
			self.fillList(items)
			self.setListFocus(nextprev, albums)
			self.setCurrentState(items)
		else:
			self.noItems('Albums')
		
		LOG('ALBUMS - STOPPED')
			
	def FRIENDS(self,uid='me'):
		LOG('FRIENDS - STARTED')
		self.saveState()
		
		self.startProgress('GETTING FRIENDS...')
		self.graph.withProgress(self.updateProgress,0.5,100,'QUERYING FACEBOOK')
		
		items = mc.ListItems()
		try:
			friends = self.graph.getObject(uid).connections.friends(fields="picture,name")
			srt = []
			show = {}
			for f in friends:
				name = f.name('')
				s = name.rsplit(' ',1)[-1] + name.rsplit(' ',1)[0]
				srt.append(s)
				show[s] = f
				srt.sort()
			total = len(srt) or 1
			ct=0
			offset = 50
			modifier = 50.0 / total
			for s in srt:
				fid = show[s].id
				tn_url = show[s].picture('').replace('_q.','_n.')
				ct+=1
				self.updateProgress(int(ct*modifier)+offset, 100, 'FRIEND %s of %s' % (ct,total))
				
				#if fid in self.imageURLCache:
				#	tn_url = self.imageURLCache[fid]
				#else:
				#	tn = "https://graph.facebook.com/"+fid+"/picture?type=large&access_token=" + self.graph.access_token
				#	tn_url = self.getRealURL(tn)
				#	self.imageURLCache[fid] = tn_url
				name = show[s].name('')
				item = mc.ListItem( mc.ListItem.MEDIA_UNKNOWN )
				item.SetLabel(ENCODE(name))
				item.SetThumbnail(ENCODE(tn_url))
				item.SetProperty('uid',uid)
				item.SetProperty('fid',ENCODE(fid))
				item.SetProperty('category','friend')
				item.SetProperty('previous',self.getSetting('last_item_name'))
				items.append(item)
				
			self.saveImageURLCache()
			self.endProgress()
		except GraphAPIError,e:
			self.endProgress()
			if not '#604' in str(e): raise
			LOG("CAN'T ACCESS USER'S FRIENDS")
		except:
			self.endProgress()
			raise
			
		if items:
			self.fillList(items)
			self.setCurrentState(items)
		else:
			self.noItems('Friends')
			
		LOG("FRIENDS - STOPPED")
		
	def PHOTOS(self,item):
		LOG("PHOTOS - STARTED")
		aid = item.GetProperty('album')
		uid = item.GetProperty('uid')
		paging = item.GetProperty('paging')
		nextprev = item.GetProperty('nextprev')
		fromUrl = item.GetProperty('from_url')
		if item.GetProperty('category') == 'photosofme': aid = uid
				
		if not paging: self.saveState()
		
		self.startProgress('GETTING PHOTOS...')
		self.graph.withProgress(self.updateProgress,0.5,100,'QUERYING FACEBOOK')
		
		items = mc.ListItems()
		try:
			if paging:
				if fromUrl:
					self.paging.append(fromUrl)
				else:
					if self.paging: paging = self.paging.pop()
				photos = self.graph.urlRequest(paging)
			else:
				self.paging = []
				photos = self.graph.getObject(aid).connections.photos()
			print photos.next
			print photos.previous
			tot = len(photos) or 1
						
			ct=0
			offset = 50
			modifier = 50.0/tot
			if photos.previous:
				item = self.getPagingItem('prev', photos.previous, 'photos')
				items.append(item)
				
			for p in photos:
				tn = p.picture('') + '?fix=' + str(time.time()) #why does this work? I have no idea. Why did I try it. I have no idea :)
				#tn = re.sub('/hphotos-\w+-\w+/\w+\.\w+/','/hphotos-ak-snc1/hs255.snc1/',tn) # this seems to get better results then using the random server
				item = mc.ListItem( mc.ListItem.MEDIA_PICTURE )
				item.SetLabel(ENCODE(self.removeCRLF(p.name(p.id))))
				source = ENCODE(p.source())
				caption = ENCODE(urllib.unquote(p.name('')))
				item.SetPath(source)
				item.SetProperty('category','photovideo')
				item.SetLabel('')
				item.SetImage(0,source)
				item.SetThumbnail(ENCODE(tn))
				item.SetProperty('uid',uid)
				#item.SetProperty('next',ENCODE(photos.next))
				#item.SetProperty('prev',ENCODE(photos.previous))
				item.SetProperty('caption',caption)
				item.SetProperty('previous',self.getSetting('last_item_name'))
				items.append(item)
				ct += 1
				self.updateProgress(int(ct*modifier)+offset,100,message='Loading photo %s of %s' % (ct,tot))
				
			if photos.next:
				item = self.getPagingItem('next', photos.next, 'photos', paging)
				items.append(item)
				
			self.endProgress()
		finally:
			self.endProgress()
		if items:
			self.fillList(items)
			self.setListFocus(nextprev, photos)
			self.setCurrentState(items)
		else:
			self.noItems('Photos',paging)
		LOG("PHOTOS - STOPPED")
	
	def VIDEOS(self,item):
		LOG("VIDEOS - STARTED")
		
		uploaded = False
		uid = item.GetProperty('uid')
		paging = item.GetProperty('paging')
		nextprev = item.GetProperty('nextprev')
		fromUrl = item.GetProperty('from_url')
		if item.GetProperty('category') != 'videosofme': uploaded = True
		
		if not paging: self.saveState()
		
		self.startProgress('GETTING VIDEOS...')
		items = mc.ListItems()
		try:
			if paging:
				if fromUrl:
					self.paging.append(fromUrl)
				else:
					if self.paging: paging = self.paging.pop()
				videos = self.graph.urlRequest(paging)
			else:
				self.paging = []
				if uploaded: videos = self.graph.getObject(uid).connections.videos__uploaded()
				else: videos = self.graph.getObject(uid).connections.videos()
			print videos.next
			print videos.previous	
			if videos.previous:
				item = self.getPagingItem('prev', videos.previous, 'videos')
				items.append(item)
				
			total = len(videos) or 1
			ct=0
			offset = 50
			modifier = 50.0/total
			for v in videos:
				item = mc.ListItem( mc.ListItem.MEDIA_VIDEO_OTHER )
				tn = v.picture('') + '?fix=' + str(time.time()) #why does this work? I have no idea. Why did I try it. I have no idea :)
				#tn = re.sub('/hphotos-\w+-\w+/\w+\.\w+/','/hphotos-ak-snc1/hs255.snc1/',tn)
				caption = ENCODE(urllib.unquote(v.name('')))
				#item.SetLabel(ENCODE(self.removeCRLF(v.get('name',v.get('id','None')))))
				#item.SetLabel('')
				item.SetPath(ENCODE(v.source('')))
				item.SetProperty('uid',uid)
				item.SetProperty('category','photovideo')
				item.SetThumbnail(ENCODE(tn))
				item.SetImage(0,ENCODE(tn))
				#item.SetProperty('next',ENCODE(videos.next))
				#item.SetProperty('prev',ENCODE(videos.previous))
				item.SetProperty('caption',caption)
				item.SetProperty('previous',self.getSetting('last_item_name'))
				items.append(item)
				ct+=1
				self.updateProgress(int(ct*modifier)+offset,100, 'Loading video %s of %s' % (ct,total))
				
			if videos.next:
				item = self.getPagingItem('next', videos.next, 'videos', paging)
				items.append(item)

		finally:
			self.endProgress()
		if items:
			self.fillList(items)
			#window.GetList(120).SetItems(items)
			self.setListFocus(nextprev, videos)
			self.setCurrentState(items)
		else:
			self.noItems('Videos',paging)
			
		LOG("VIDEOS - STOPPED")
		
	def noItems(self,itype='items',paging=None):
		self.popState(clear=True)
		message = "No %s or not authorized." % itype
		if paging: message = 'End of %s reached.' % itype
		mc.ShowDialogOk("None Available", message)
		
	def saveImageURLCache(self):
		out = ''
		for k in self.imageURLCache:
			out += '%s=%s\n' % (k,self.imageURLCache[k])
				
		cache_file = os.path.join(self.CACHE_PATH,'imagecache')

		f = open(cache_file,"w")
		f.write(out)
		f.close()
		
	def loadImageURLCache(self):
		cache_file = os.path.join(self.CACHE_PATH,'facebook-media','imagecache')
		if not os.path.exists(cache_file): return
		
		f = open(cache_file,"r")
		data = f.read()
		f.close()
		
		for line in data.splitlines():
			k,v = line.split('=',1)
			self.imageURLCache[k] = v
		
	def mediaNextPrev(self,np):
		LOG("PHOTOS - %s" % np.upper())
		item = mc.GetActiveWindow().GetList(120).GetItem(0)
		url = item.GetProperty(np)
		print "%s URL: %s" % (np.upper(),url)
		if url:
			if self.itemType(item) == 'image':
				self.PHOTOS(url, isPaging=True)
			else:
				self.VIDEOS(url, isPaging=True)
			if np == 'prev':
				list = mc.GetWindow(14001).GetList(120)
				idx = len(list.GetItems()) - 1
				if idx < 0: idx = 0
				mc.GetWindow(14001).GetList(120).SetFocusedItem(idx)
		
	def mediaNext(self):
		self.mediaNextPrev('next')
	
	def mediaPrev(self):
		self.mediaNextPrev('prev')

	def menuItemSelected(self,select=False):
		try:
			item = self.getFocusedItem(120)
			
			cat = item.GetProperty('category')
			uid = item.GetProperty('uid') or 'me'
			
			if cat == 'friend':
				name = item.GetLabel()
				self.CATEGORIES(item.GetProperty('fid'),name)
				self.setFriend(name)
				self.setSetting('last_item_name',item.GetLabel())
				self.setPathDisplay()
				return
			else:
				if uid == 'me': self.setFriend()
				
			if cat == 'albums':
				self.ALBUMS(item)
			elif cat == 'photos':
				self.PHOTOS(item)
			elif cat == 'friends':
				self.FRIENDS(uid)
			elif cat == 'videos':
				self.VIDEOS(item)
			elif cat == 'photosofme':
				self.PHOTOS(item)
			elif cat == 'videosofme':
				self.VIDEOS(item)
			elif cat == 'photovideo':
				if not select:
					if self.showPhotoMenu():
						return
				self.setCurrentState()
				self.setFriend('')
				self.showMedia(item)
			elif cat == 'paging':
				self.setSetting('last_item_name',item.GetProperty('previous'))
				if item.GetProperty('mediatype') == 'photos': 		self.PHOTOS(item)
				elif item.GetProperty('mediatype') == 'videos': 	self.VIDEOS(item)
				elif item.GetProperty('mediatype') == 'albums': 	self.ALBUMS(item)
				return
			
			self.setSetting('last_item_name',item.GetLabel())
			self.setPathDisplay()
		except:
			message = ERROR('UNHANDLED ERROR')
			mc.ShowDialogOk('ERROR',message)
		
	def menuItemDeSelected(self):
		if not self.popState():
			mc.GetWindow(14001).GetControl(125).SetFocus()
	
	def optionMenuItemSelected(self):
		print "OPTION ITEM SELECTED"
		item = self.getFocusedItem(125)
		mc.GetWindow(14001).GetControl(120).SetFocus()
		uid = item.GetProperty('uid')
		if uid:
			self.setCurrentUser(uid)
		else:
			action = item.GetProperty('action')
			if action == 'add_user':
				self.openAddUserWindow()
			elif action == 'remove_user':
				self.removeUserMenu()
		
	def showPhotoMenu(self):
		return False
	
	def removeUserMenu(self):
		import xbmcgui #@UnresolvedImport
		uids = self.getUserList()
		options = []
		for uid in uids: options.append(self.getSetting('username_%s' % uid))

		idx = xbmcgui.Dialog().select('Choose User To Remove',options)
		if idx < 0:
			return
		else:
			uid = uids[idx]
			self.removeUser(uid)		
		
	def removeUser(self,uid):
		self.removeUserFromList(uid)
		self.clearSetting('login_email_%s' % uid)
		self.clearSetting('login_pass_%s' % uid)
		self.clearSetting('token_%s' % uid)
		self.clearSetting('profile_pic_%s' % uid)
		self.clearSetting('username_%s' % uid)
		self.setSetting('current_user','')
		self.currentUser = None
		self.getCurrentUser()
		self.loadOptions()
		
	def setPathDisplay(self):
		path = []
		for state in self.states:
			path.append(state.settings.get('last_item_name'))
		path.append(self.getSetting('last_item_name'))
		path = ' : '.join(path[1:])
		self.setSetting('current_nav_path',path)
		LOG('PATH - %s' % path)
		
	def setFriend(self,name=''):
		self.setSetting('current_friend_name',name)
		
	def startProgress(self,message):
		mc.GetWindow(14001).GetControl(160).SetFocus()
		mc.ShowDialogWait()
		mc.GetWindow(14001).GetLabel(152).SetLabel(message)
		self.setSetting('progress','0')
		
	def updateProgress(self,ct,total,message=''):
		if ct < 0 or ct > total:
			LOG('PROGRESS OUT OF BOUNDS')
			return
		pct = int((ct / float(total)) * 20) * 5
		window = mc.GetWindow(14001)
		self.setSetting('progress',str(pct))
		window.GetLabel(152).SetLabel(message)
	
	def endProgress(self):
		self.setSetting('progress','')
		mc.HideDialogWait()
		mc.GetWindow(14001).GetControl(120).SetFocus()
	
	def showImages(self,items,number=0):
		LOG('SHOW IMAGES')
		mc.GetPlayer().PlaySlideshow(items, True, False, str(number), True)
		
	def showImage(self,item):
		items = mc.ListItems()
		items.append(item)
		self.showImages(items)
		
	def showVideo(self,item):
		mc.GetPlayer().Play(item)
		
	def showMedia(self,item):
		if self.itemType(item) == 'image':
			self.showImage(item)
		else:
			self.showVideo(item)
		
	def itemType(self,item):
		mtype = item.GetMediaType()
		if mtype == mc.ListItem.MEDIA_PICTURE:
			return 'image'
		elif mtype == mc.ListItem.MEDIA_VIDEO_OTHER:
			return 'video'
		else:
			return 'other'
	
	def getFocusedItem(self,list_id):
		lc = mc.GetActiveWindow().GetList(list_id)
		itemNumber = lc.GetFocusedItem()
		self.lastItemNumber = itemNumber
		return lc.GetItem(itemNumber)
	
	def removeCRLF(self,text):
		return " ".join(text.split())
		
	def makeAscii(self,name):
		return name.encode('ascii','replace')
	
	def getFile(self,url,target_file):
		try:
			request = urllib2.urlopen(url)
			target_file = self.fixExtension(request.info().get('content-type',''),target_file)
		except:
			print 'ERROR: urlopen() in getFile()'
			return ''
		f = open(target_file,"wb")
		f.write(request.read())
		f.close()
		return target_file
	
	def fixExtension(self,content_type,fn):
		if not 'image' in content_type: return
		ext = content_type.split('/',1)[-1]
		if not ext in 'jpeg,png,gif,bmp': return
		if ext == 'jpeg': ext = 'jpg'
		fn = os.path.splitext(fn)[0] + '.' + ext
		return fn
	
	def addUser(self,email=None,password=None):
		if self.newUserCache:
			self.addUserPart2()
			return
		LOG("ADD USER PART 1")
		self.setSetting('auth_step_1','pending')
		if not email:
			email = doKeyboard("Login Email")
		if not email:
			mc.CloseWindow()
			return
		if not password:
			password = doKeyboard("Login Password",hidden=True)
		if not password:
			mc.CloseWindow()
			return
		self.newUserCache = (email,password)
		self.getAuth()
		
	def addUserPart2(self):
		LOG("ADD USER PART 2")
		self.setSetting('auth_step_1','complete')
		self.setSetting('auth_step_2','pending')
		email,password = self.newUserCache
		self.newUserCache = None
		graph = self.newGraph(email, password)
		graph.getNewToken()
		self.setSetting('auth_step_2','complete')
		self.setSetting('auth_step_3','pending')
		user = graph.getObject('me',fields='id,name,picture')
		self.setSetting('auth_step_3','complete')
		uid = user.id
		username = user.name()
		if not self.addUserToList(uid):
			LOG("USER ALREADY ADDED")
		self.setSetting('login_email_%s' % uid,email)
		self.setSetting('login_pass_%s' % uid,password)
		self.setSetting('username_%s' % uid,username)
		self.setSetting('token_%s' % uid,graph.access_token)
		#if self.token: self.setSetting('token_%s' % uid,self.token)
		self.setSetting('auth_step_4','pending')
		self.setSetting('profile_pic_%s' % uid,user.picture('').replace('_q.','_n.'))
		#self.getProfilePic(uid,force=True)
		self.setSetting('auth_step_4','complete')
		mc.ShowDialogOk("User Added",ENCODE(username))
		mc.CloseWindow()
		self.loadOptions()
		if not self.getSetting('has_user'):
			self.setSetting('has_user','true')
			self.start()
		#self.setCurrentUser(uid)
		return uid
	
	def getUserList(self):
		ustring = self.getSetting('user_list')
		if not ustring: return []
		return ustring.split(',')
	
	def getUsers(self):
		ulist = []
		for uid in self.getUserList():
			ulist.append(FacebookUser(uid))
		return ulist
	
	def addUserToList(self,uid):
		ulist = self.getUserList()
		if uid in ulist: return False
		ulist.append(uid)
		self.setSetting('user_list',','.join(ulist))
		return True
	
	def removeUserFromList(self,uid):
		ulist = self.getUserList()
		if not uid in ulist: return
		new = []
		for u in ulist:
			if u != uid: new.append(u)
		self.setSetting('user_list',','.join(new))
		
	def setCurrentUser(self,uid):
		self.currentUser = FacebookUser(uid)
		self.setSetting('current_user', uid)
		u = self.currentUser
		self.setSetting('current_user_name', u.username)
		self.updateUserPic()
		if self.graph: self.graph.setLogin(u.email,u.password,u.id,u.token)
		
	def getCurrentUser(self):
		if self.currentUser: return self.currentUser
		uid = self.getSetting('current_user')
		if not uid:
			ulist = self.getUserList()
			if ulist:
				uid = ulist[0]
				if uid: self.setCurrentUser(uid)
		print uid
		if not uid: return None
		self.currentUser = FacebookUser(uid)
		self.setSetting('current_user_name', self.currentUser.username)
		self.updateUserPic()
		return self.currentUser
	
	def updateUserPic(self):
		self.setSetting('current_user_pic','')
		outfile = os.path.join(self.CACHE_PATH,'current_user_pic')
		self.setSetting('current_user_pic',self.getFile(self.currentUser.pic,outfile))
		
	def getProfilePic(self,uid,force=False):
		url = "https://graph.facebook.com/%s/picture?type=large" % uid
		fbase = binascii.hexlify(uid.encode('utf-8'))
		fn = os.path.join(self.CACHE_PATH,fbase + '.jpg')
		if not force:
			current_pic = self.getSetting('profile_pic_%s' % uid)
			if current_pic and os.path.exists(current_pic): return current_pic
		try:
			fn = self.getFile(url,fn)
			self.setSetting('profile_pic_%s' % uid,fn)
			return fn
		except:
			LOG('ERROR GETTING PROFILE PIC AT: ' % url)
			return ''
			
	def clearSetting(self,key):
		mc.GetApp().GetLocalConfig().Reset(str(key))
		
	def setSetting(self,key,value):
		mc.GetApp().GetLocalConfig().SetValue(str(key),str(value))
		
	def getSetting(self,key):
		return mc.GetApp().GetLocalConfig().GetValue(key)
	
	def getAuth(self,email='',password=''):
		redirect = urllib.quote('http://2ndmind.com/facebookphotos/complete.html')
		scope = urllib.quote('user_photos,friends_photos,user_photo_video_tags,friends_photo_video_tags,user_videos,friends_videos')
		url = 'https://graph.facebook.com/oauth/authorize?client_id=150505371652086&redirect_uri=%s&type=user_agent&scope=%s' % (redirect,scope)
				
		launchBoxeeBrowser(url,email=email,password=password)
		#token = fb.graph.extractTokenFromURL(url)
		#if fb.graph.tokenIsValid(token):
		#	fb.graph.saveToken(token)
		#	return token
		#return None

def launchBoxeeBrowser(url,**kwargs):
	from urllib import quote
	from urlparse import urlparse,urlunparse
	
	uri = urlparse(url)

	if not uri[0]:
		url = "http://"+urlunparse(uri)
		uri = urlparse(url)

	domain = uri[1]
	domain = domain.split('.')

	if len(domain) > 2:
		domain = domain[-2:]

	domain = ".".join(domain)

	args = ''
	for k in kwargs:
		args += '&%s=%s' % (k,quote(kwargs[k]))
		
	#path = 'flash://%s/src=%s%s&bx-jsactions=%s' % (domain, quote(url),args,quote('http://dir.boxee.tv/apps/browser/browser.js'))
	path = 'flash://%s/src=%s%s&bx-jsactions=%s' % (domain, quote(url),args,quote('http://2ndmind.com/boxee/facebook-media/fbauth.js'))
	
	item = mc.ListItem()
	item.SetLabel("Authorize")
	item.SetAddToHistory(False)
	item.SetReportToServer(False)
	item.SetContentType("application/x-shockwave-flash")
	item.SetPath(path)
	player = mc.Player()
	player.Play(item)
		
def doKeyboard(prompt,default='',hidden=False):
	return mc.ShowDialogKeyboard(prompt,default,hidden)

BOXEE_VERSION = mc.GetInfoString('System.BuildVersion')
LOG('Boxee Version: %s' % BOXEE_VERSION)

params = mc.Parameters()
params['none'] = 'NONE'

config = mc.GetApp().GetLocalConfig()
config.SetValue('current_user_pic','facebook-media-icon-generic-user.png')
config.SetValue('current_friend_name','')
config.SetValue('progress','')
config.SetValue('last_item_name','OPTIONS')
config.SetValue('current_nav_path','')

CLOSEREADY = False
mc.GetApp().ActivateWindow(14000,params)
