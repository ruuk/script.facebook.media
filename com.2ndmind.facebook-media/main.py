import mc #@UnresolvedImport
import re,os,binascii,urllib,urllib2,time

#import traceback
import facebook

import locale
loc = locale.getdefaultlocale()
print loc
ENCODING = loc[1] or 'utf-8'

def ENCODE(string):
	return string.encode(ENCODING,'replace')

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
		
class FacebookSession:
	def __init__(self):
		self.lastItemNumber = 0
		self.CACHE_PATH = mc.GetTempDir()
		self.newUserCache = None
		self.currentUser = None
		self.setFriend()
		
		self.imageURLCache = {}
		self.loadImageURLCache()
				
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
		print user.email
		
		self.CATEGORIES()
		
	def newGraph(self,email,password,uid=None,token=None,new_token_callback=None):
		graph = facebook.GraphWrap(token,new_token_callback=new_token_callback)
		graph.setAppData('150505371652086',scope='user_photos,friends_photos,user_photo_video_tags,friends_photo_video_tags')
		graph.setLogin(email,password,uid)
		return graph
		
	def newTokenCallback(self,token):
		self.token = token
		if self.currentUser: self.currentUser.updateToken(token)
		
	def changeAddUser(self):
		import xbmcgui #@UnresolvedImport
		uids = self.getUserList()
		options = []
		for uid in uids: options.append(self.getSetting('username_%s' % uid))
		options.append('Add User')

		idx = xbmcgui.Dialog().select('Options',options)
		if idx < 0:
			return
		elif idx == len(options) -1:
			self.openAddUserWindow()
			return
		else:
			uid = uids[idx]
			self.setCurrentUser(uid)
		
		
	def openAddUserWindow(self):
		params = mc.Parameters()
		params['test'] = 'ATEST'
		self.setSetting('auth_step_1','')
		self.setSetting('auth_step_2','')
		self.setSetting('auth_step_3','')
		self.setSetting('auth_step_4','')
		mc.GetApp().ActivateWindow(14001,params)
			
	def CATEGORIES(self,uid='me',name=''):
		print "FACEBOOK MEDIA CATEGORIES - STARTED"
		window = mc.GetWindow(14000)
		
		items = mc.ListItems()
		cids = ('albums','videos','friends','photosofme','videosofme','changeuser')
		if uid == 'me':
			cats = ('ALBUMS','VIDEOS','FRIENDS','PHOTOS OF ME','VIDEOS OF ME','MANAGE USERS')
		else:
			cats = ('ALBUMS','VIDEOS','FRIENDS','PHOTOS OF USER','VIDEOS OF USER')
			cids = ('albums','videos','friends','photosofme','videosofme')
			
		for cat,cid in zip(cats,cids):
			item = mc.ListItem( mc.ListItem.MEDIA_UNKNOWN )
			#item.SetContentType("")
			item.SetLabel(cat)
			#item.SetDescription(desc)
			item.SetPath(cid)
			item.SetProperty('uid',uid)
			item.SetThumbnail('facebook-media-icon-%s.png' % cid)
			item.SetProperty('background','')
			items.append(item)
		
		mc.HideDialogWait()
		if uid != 'me':
			window.PushState()
			mc.GetWindow(14000).GetControl(180).SetVisible(True)
		window.GetList(120).SetItems(items)
		window.GetControl(120).SetFocus()
		print "FACEBOOK MEDIA CATEGORIES - STOPPED"

	def ALBUMS(self,uid='me',name=''):
		print "FACEBOOK MEDIA ALBUMS - STARTED"
		window = mc.GetWindow(14000)
		
		self.startProgress('GETTING ALBUMS...')
			
		try:
			albums = self.graph.connections.albums(id=uid)
			items = mc.ListItems()
			total = len(albums['data'])
			ct = 0
			for a in albums['data']:
				ct += 1
				self.updateProgress(ct, total,'ALBUM %s OF %s' % (ct,total))
				aid = a.get('id','')
				#fbase = binascii.hexlify(aid.encode('utf-8'))
				#fn = os.path.join(self.CACHE_PATH,fbase + '.jpg') #still works even if image is not jpg - doesn't work without the extension
				if aid in self.imageURLCache:
					tn_url = self.imageURLCache[aid]
				else:
					tn = "https://graph.facebook.com/"+aid+"/picture?access_token=" + self.graph.access_token
					req = urllib2.urlopen(tn)
					tn_url = req.geturl()
					self.imageURLCache[aid] = tn_url
#				if not os.path.exists(fn):
#					#if self.get_album_photos:
#					if True: fn = self.getFile(str(tn),str(fn))
#					else: fn = ''
				aname = a.get('name','').encode('ISO-8859-1','replace')
				
				item = mc.ListItem( mc.ListItem.MEDIA_UNKNOWN )
				item.SetLabel(aname)
				item.SetThumbnail(ENCODE(tn_url))
				item.SetImage(0,ENCODE(tn_url))
				#item.SetProperty('background',str(tn_url))
				item.SetProperty('album',ENCODE(aid))
				item.SetPath('photos')
				items.append(item)
			self.saveImageURLCache()
		finally:
			self.endProgress()
			window.GetControl(120).SetFocus()
	
		window.PushState()
		if items: window.GetList(120).SetItems(items)
		window.GetControl(120).SetFocus()
		
		print "FACEBOOK MEDIA ALBUMS - STOPPED"
			
#		if uid != 'me':
#			self.addDir(	self.lang(30012).replace('@REPLACE@',name),
#							os.path.join(self.IMAGES_PATH,'videos.png'),
#							url=uid,
#							mode=3)
#			self.addDir(self.lang(30007).replace('@REPLACE@',name),os.path.join(self.IMAGES_PATH,'photosofme.png'),url=uid,mode=101)
#			self.addDir(self.lang(30013).replace('@REPLACE@',name),os.path.join(self.IMAGES_PATH,'videosofme.png'),url=uid,mode=102)

	def FRIENDS(self,uid='me'):
		print "FACEBOOK MEDIA FRIENDS - STARTED"
		window = mc.GetWindow(14000)
		
		self.startProgress('GETTING FRIENDS...')
		
		try:
			friends = self.graph.connections.friends(uid)
			srt = []
			show = {}
			items = mc.ListItems()
			for f in friends['data']:
				name = f.get('name','')
				s = name.rsplit(' ',1)[-1] + name.rsplit(' ',1)[0]
				srt.append(s)
				show[s] = f
				srt.sort()
			total = len(srt)
			ct=0
			for s in srt:
				uid = show[s].get('id','')
				#fbase = binascii.hexlify(uid.encode('utf-8'))
				#fn = os.path.join(self.CACHE_PATH,fbase + '.jpg') #still works even if image is not jpg - doesn't work without the extension
				ct+=1
				self.updateProgress(ct, total, 'FRIEND %s of %s' % (ct,total))
				
				if uid in self.imageURLCache:
					tn_url = self.imageURLCache[uid]
				else:
					tn = "https://graph.facebook.com/"+uid+"/picture?type=large&access_token=" + self.graph.access_token
					req = urllib2.urlopen(tn)
					tn_url = req.geturl()
					self.imageURLCache[uid] = tn_url
				#print fn
#				if not os.path.exists(fn):
#					#if self.get_friends_photos:
#					if True:
#						try:
#							fn = self.getFile(tn,fn)
#						except:
#							fn = ''
#					else:
#						fn = ''
				#fn = "https://graph.facebook.com/"+uid+"/picture?access_token=" + self.graph.access_token + "&nonsense=image.jpg" #<-- crashes XBMC
				name = show[s].get('name','')
				item = mc.ListItem( mc.ListItem.MEDIA_UNKNOWN )
				item.SetLabel(ENCODE(name))
				item.SetThumbnail(ENCODE(tn_url))
				item.SetProperty('uid',ENCODE(uid))
				item.SetPath('friend')
				items.append(item)
				
			self.saveImageURLCache()
		finally:
			self.endProgress()
			
		window.PushState()
		if items: window.GetList(120).SetItems(items)
		window.GetControl(120).SetFocus()
			
	def PHOTOS(self,aid,isPaging=False):
		print "FACEBOOK MEDIA PHOTOS - STARTED: %s" % aid 
		window = mc.GetWindow(14000)
		if not isPaging: window.PushState()
		
		self.startProgress('GETTING PHOTOS...')

		try:
			if isPaging:
				photos = self.graph.request(aid)
			else:
				photos = self.graph.connections.photos(aid)
			tot = len(photos['data'])
			items = mc.ListItems()
			
			prev,next = self.getPaging(photos)
			
			ct=0
			for p in photos['data']:
				tn = p.get('picture','') + '?fix=' + str(time.time()) #why does this work? I have no idea. Why did I try it. I have no idea :)
				tn = re.sub('/hphotos-\w+-\w+/\w+\.\w+/','/hphotos-ak-snc1/hs255.snc1/',tn) # this seems to get better results then using the random server
				item = mc.ListItem( mc.ListItem.MEDIA_PICTURE )
				item.SetLabel(ENCODE(self.removeCRLF(p.get('name',p.get('id','None')))))
				source = ENCODE(p.get('source',''))
				caption = ENCODE(urllib.unquote(p.get('name','')))
				item.SetPath(source)
				item.SetImage(0,source)
				item.SetThumbnail(ENCODE(tn))
				item.SetProperty('next',ENCODE(next))
				item.SetProperty('prev',ENCODE(prev))
				item.SetProperty('caption',caption)
				items.append(item)
				ct += 1
				self.updateProgress(ct,tot,message='Loading photo %s of %s' % (ct,tot))

			self.endProgress()
			window.GetList(121).SetItems(items)
		finally:
			self.endProgress()
			window.GetControl(121).SetVisible(True)
			window.GetControl(121).SetEnabled(True)
			window.GetControl(121).SetFocus()
		
		print "FACEBOOK MEDIA PHOTOS - STOPPED"
	
	def VIDEOS(self,uid,uploaded=False,isPaging=False):
		print "FACEBOOK MEDIA VIDEOS - STARTED"
		window = mc.GetWindow(14000)
		if not isPaging: window.PushState()
		
		self.startProgress('GETTING VIDEOS...')
		try:
			if isPaging:
				videos = self.graph.request(uid)
			else:
				if uploaded: videos = self.graph.connections.videos__uploaded(uid)
				else: videos = self.graph.connections.videos(uid)
			total = len(videos['data'])
			items = mc.ListItems()
			
			prev,next = self.getPaging(videos)
			ct=0
			for v in videos['data']:
				item = mc.ListItem( mc.ListItem.MEDIA_VIDEO_OTHER )
				tn = v.get('picture','') + '?fix=' + str(time.time()) #why does this work? I have no idea. Why did I try it. I have no idea :)
				tn = re.sub('/hphotos-\w+-\w+/\w+\.\w+/','/hphotos-ak-snc1/hs255.snc1/',tn)
				caption = ENCODE(urllib.unquote(v.get('name','')))
				item.SetLabel(ENCODE(self.removeCRLF(v.get('name',v.get('id','None')))))
				item.SetPath(ENCODE(v.get('source','')))
				item.SetThumbnail(ENCODE(tn))
				item.SetImage(0,ENCODE(tn))
				item.SetProperty('next',ENCODE(next))
				item.SetProperty('prev',ENCODE(prev))
				item.SetProperty('caption',caption)
				items.append(item)
				ct+=1
				self.updateProgress(ct, total, 'Loading video %s of %s' % (ct,total))
			window.GetList(121).SetItems(items)
		finally:
			self.endProgress()
			window.GetControl(121).SetVisible(True)
			window.GetControl(121).SetEnabled(True)
			window.GetControl(121).SetFocus()
		
		
	def getPaging(self,obj):
		paging = obj.get('paging')
		next = ''
		prev = ''
		if paging:
			next = paging.get('next','')
			prev = paging.get('previous','')
			if self.areAlmostTheSame(prev,next):
				prev = ''
				next = ''
		return prev,next
		
	def saveImageURLCache(self):
		out = ''
		for k in self.imageURLCache:
			out += '%s=%s\n' % (k,self.imageURLCache[k])
		
		cache_file_path = os.path.join(self.CACHE_PATH,'facebook-media')
		if not os.path.exists(cache_file_path): os.makedirs(cache_file_path)
		cache_file = os.path.join(cache_file_path,'imagecache')

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
		print "FACEBOOK MEDIA PHOTOS - %s" % np.upper()
		item = mc.GetActiveWindow().GetList(121).GetItem(0)
		url = item.GetProperty(np)
		print "%s URL: %s" % (np.upper(),url)
		if url:
			if self.itemType(item) == 'image':
				self.PHOTOS(url, isPaging=True)
			else:
				self.VIDEOS(url, isPaging=True)
			if np == 'prev':
				list = mc.GetWindow(14000).GetList(121)
				idx = len(list.GetItems()) - 1
				if idx < 0: idx = 0
				mc.GetWindow(14000).GetList(121).SetFocusedItem(idx)
		
	def mediaNext(self):
		self.mediaNextPrev('next')
	
	def mediaPrev(self):
		self.mediaNextPrev('prev')

	def menuItemSelected(self):
		itemNumber = mc.GetActiveWindow().GetList(120).GetFocusedItem()
		item = mc.GetActiveWindow().GetList(120).GetItem(itemNumber)
		
		cat = item.GetPath()
		uid = item.GetProperty('uid') or 'me'
		
		if cat == 'friend':
			name = item.GetLabel()
			self.setFriend(name)
			self.CATEGORIES(uid,name)
			return
		else:
			if uid == 'me': self.setFriend()
			
		if cat == 'albums':
			self.ALBUMS(uid=uid)
		elif cat == 'photos':
			self.PHOTOS(item.GetProperty('album'))
		elif cat == 'friends':
			self.FRIENDS(uid)
		elif cat == 'videos':
			self.VIDEOS(uid,uploaded=True)
		elif cat == 'photosofme':
			self.PHOTOS(uid)
		elif cat == 'videosofme':
			self.VIDEOS(uid)
		elif cat == 'changeuser':
			self.changeAddUser()
	
	def setFriend(self,name=''):
		self.setSetting('current_friend_name',name)
		
	def startProgress(self,message):
		mc.ShowDialogWait()
		self.updateProgress(0,1)
		window = mc.GetWindow(14000)
		window.GetImage(150).SetVisible(True)
		window.GetControl(160).SetEnabled(True)
		#window.GetControl(160).SetFocus()
		window.GetLabel(152).SetLabel(message)
		
	def updateProgress(self,ct,total,message=''):
		if ct < 0 or ct > total:
			print 'FACBOOK MEDIA - PROGRESS OUT OF BOUNDS'
			return
		pct = int((ct / float(total)) * 10) * 10
		window = mc.GetWindow(14000)
		window.GetImage(151).SetTexture('facebook-media-progress-bar-%s.png' % pct)
		window.GetLabel(152).SetLabel(message)
	
	def endProgress(self):
		window = mc.GetWindow(14000)
		window.GetImage(150).SetVisible(False)
		window.GetControl(160).SetEnabled(False)
		window.GetControl(160).SetVisible(False)
		mc.HideDialogWait()
	
	def showImages(self,items,number=0):
		print 'FACEBOOK MEDIA SHOW IMAGES'
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
		
	def areAlmostTheSame(self,first,second):
		if not first or not second: return False
		first = re.sub('(\d{4}-\d{2}-\d{2}T\d{2}%3A\d{2}%3A\d)\d(%2B\d{4})',r'\1x\2',first)
		second = re.sub('(\d{4}-\d{2}-\d{2}T\d{2}%3A\d{2}%3A\d)\d(%2B\d{4})',r'\1x\2',second)
		return first == second
	
	def removeCRLF(self,text):
		return " ".join(text.split())
		
	def makeAscii(self,name):
		return name.encode('ascii','replace')
	
	def getFile(self,url,target_file):
		try:
			request = urllib2.urlopen(url)
		except:
			print 'ERROR: urlopen() in getFile()'
			return ''
		f = open(target_file,"wb")
		f.write(request.read())
		f.close()
		return target_file
	
	def addUser(self,email=None,password=None):
		if self.newUserCache:
			self.addUserPart2()
			return
		print "FACEBOOK MEDIA - ADD USER PART 1"
		self.setSetting('auth_step_1','pending')
		if not email:
			email = doKeyboard("Login Email")
		if not email: return None
		if not password:
			password = doKeyboard("Login Password",hidden=True)
		if not password: return None
		self.newUserCache = (email,password)
		self.getAuth()
		
	def addUserPart2(self):
		print "FACEBOOK MEDIA - ADD USER PART 2"
		self.setSetting('auth_step_1','complete')
		self.setSetting('auth_step_2','pending')
		email,password = self.newUserCache
		self.newUserCache = None
		graph = self.newGraph(email, password)
		graph.getNewToken()
		self.setSetting('auth_step_2','complete')
		self.setSetting('auth_step_3','pending')
		user = graph.object.me()
		self.setSetting('auth_step_3','complete')
		print user
		uid = user['id']
		username = user['name']
		if not self.addUserToList(uid):
			print "FACEBOOK MEDIA - USER ALREADY ADDED"
		self.setSetting('login_email_%s' % uid,email)
		self.setSetting('login_pass_%s' % uid,password)
		self.setSetting('username_%s' % uid,username)
		self.setSetting('token_%s' % uid,graph.access_token)
		#if self.token: self.setSetting('token_%s' % uid,self.token)
		self.setSetting('auth_step_4','pending')
		self.getProfilePic(uid)
		self.setSetting('auth_step_4','complete')
		mc.ShowDialogOk("User Added",ENCODE(username))
		mc.CloseWindow()
		if not self.getSetting('has_user'):
			self.setSetting('has_user','true')
			self.start()
		#self.setCurrentUser(uid)
		return uid
	
	def getUserList(self):
		ustring = self.getSetting('user_list')
		if not ustring: return []
		return ustring.split(',')
	
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
		self.setSetting('current_user_pic', u.pic)
		self.graph.setLogin(u.email,u.password,u.id,u.token)
		
	def getCurrentUser(self):
		if self.currentUser: return self.currentUser
		uid = self.getSetting('current_user')
		if not uid:
			ulist = self.getUserList()
			if ulist: uid = ulist[0]
		print uid
		if not uid: return None
		self.currentUser = FacebookUser(uid)
		self.setSetting('current_user_name', self.currentUser.username)
		self.setSetting('current_user_pic', self.currentUser.pic)
		return self.currentUser
	
	def getProfilePic(self,uid):
		url = "https://graph.facebook.com/%s/picture?type=large" % uid
		fbase = binascii.hexlify(uid.encode('utf-8'))
		fn = os.path.join(self.CACHE_PATH,fbase + '.jpg')
		try:
			fn = self.getFile(url,fn)
			self.setSetting('profile_pic_%s' % uid,fn)
		except:
			print 'FACEBOOK MEDIA - ERROR GETTING PROFILE PIC AT: ' % url
			
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

params = mc.Parameters()
params['none'] = 'NONE'
mc.GetApp().ActivateWindow(14000,params)

session = FacebookSession()
