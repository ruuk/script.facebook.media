#!/usr/bin/env python
#
# Copyright 2010 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#	 http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Python client library for the Facebook Platform.

This client library is designed to support the Graph API and the official
Facebook JavaScript SDK, which is the canonical way to implement
Facebook authentication. Read more about the Graph API at
http://developers.facebook.com/docs/api. You can download the Facebook
JavaScript SDK at http://github.com/facebook/connect-js/.

If your application is using Google AppEngine's webapp framework, your
usage of this module might look like this:

	user = facebook.get_user_from_cookie(self.request.cookies, key, secret)
	if user:
		graph = facebook.GraphAPI(user["access_token"])
		profile = graph.get_object("me")
		friends = graph.get_connections("me", "friends")

"""

import urllib
import sys, re

# Find a JSON parser
try:
	import json
	_parse_json = lambda s: json.loads(s)
except ImportError:
	try:
		import simplejson
		_parse_json = lambda s: simplejson.loads(s)
	except ImportError:
		# For Google AppEngine
		from django.utils import simplejson
		_parse_json = lambda s: simplejson.loads(s)


class GraphAPI(object):
	"""A client for the Facebook Graph API.

	See http://developers.facebook.com/docs/api for complete documentation
	for the API.

	The Graph API is made up of the objects in Facebook (e.g., people, pages,
	events, photos) and the connections between them (e.g., friends,
	photo tags, and event RSVPs). This client provides access to those
	primitive types in a generic way. For example, given an OAuth access
	token, this will fetch the profile of the active user and the list
	of the user's friends:

	   graph = facebook.GraphAPI(access_token)
	   user = graph.get_object("me")
	   friends = graph.get_connections(user["id"], "friends")

	You can see a list of all of the objects and connections supported
	by the API at http://developers.facebook.com/docs/reference/api/.

	You can obtain an access token via OAuth or by using the Facebook
	JavaScript SDK. See http://developers.facebook.com/docs/authentication/
	for details.

	If you are using the JavaScript SDK, you can use the
	get_user_from_cookie() method below to get the OAuth access token
	for the active user from the cookie saved by the SDK.
	"""
	def __init__(self, access_token=None):
		self.access_token = access_token

	def get_object(self, id, **args):
		"""Fetchs the given object from the graph."""
		return self.request(id, args)

	def get_objects(self, ids, **args):
		"""Fetchs all of the given object from the graph.

		We return a map from ID to object. If any of the IDs are invalid,
		we raise an exception.
		"""
		args["ids"] = ",".join(ids)
		return self.request("", args)

	def get_connections(self, id, connection_name, **args):
		"""Fetchs the connections for given object."""
		return self.request(id + "/" + connection_name, args)

	def put_object(self, parent_object, connection_name, **data):
		"""Writes the given object to the graph, connected to the given parent.

		For example,

			graph.put_object("me", "feed", message="Hello, world")

		writes "Hello, world" to the active user's wall. Likewise, this
		will comment on a the first post of the active user's feed:

			feed = graph.get_connections("me", "feed")
			post = feed["data"][0]
			graph.put_object(post["id"], "comments", message="First!")

		See http://developers.facebook.com/docs/api#publishing for all of
		the supported writeable objects.

		Most write operations require extended permissions. For example,
		publishing wall posts requires the "publish_stream" permission. See
		http://developers.facebook.com/docs/authentication/ for details about
		extended permissions.
		"""
		assert self.access_token, "Write operations require an access token"
		return self.request(parent_object + "/" + connection_name, post_args=data)

	def put_wall_post(self, message, attachment={}, profile_id="me"):
		"""Writes a wall post to the given profile's wall.

		We default to writing to the authenticated user's wall if no
		profile_id is specified.

		attachment adds a structured attachment to the status message being
		posted to the Wall. It should be a dictionary of the form:

			{"name": "Link name"
			 "link": "http://www.example.com/",
			 "caption": "{*actor*} posted a new review",
			 "description": "This is a longer description of the attachment",
			 "picture": "http://www.example.com/thumbnail.jpg"}

		"""
		return self.put_object(profile_id, "feed", message=message, **attachment)

	def put_comment(self, object_id, message):
		"""Writes the given comment on the given post."""
		return self.put_object(object_id, "comments", message=message)

	def put_like(self, object_id):
		"""Likes the given post."""
		return self.put_object(object_id, "likes")

	def delete_object(self, id):
		"""Deletes the object with the given ID from the graph."""
		self.request(id, post_args={"method": "delete"})

	def request(self, path, args=None, post_args=None):
		"""Fetches the given path in the Graph API.

		We translate args to a valid query string. If post_args is given,
		we send a POST request to the given path with the given arguments.
		"""
		if not args: args = {}
		if self.access_token:
			if post_args is not None:
				post_args["access_token"] = self.access_token
			else:
				args["access_token"] = self.access_token
		if post_args is None: post_data = None
		else: urllib.urlencode(post_args)
		pre = "https://graph.facebook.com/"
		args = "?" + urllib.urlencode(args)
		if path.startswith('http'):
			pre = ''
			args = ''
		fileob = urllib.urlopen(pre + path + args, post_data)
		try:
			response = _parse_json(fileob.read())
		finally:
			fileob.close()

		if response.get("error"):
			raise GraphAPIError(response["error"]["type"],
								response["error"]["message"])
		return response


class GraphAPIError(Exception):
	def __init__(self, type, message):
		Exception.__init__(self, message)
		self.type = type

class GraphWrapAuthError(Exception):
	def __init__(self, type, message):
		Exception.__init__(self, message)
		self.type = type
		self.message = message

class GraphObject:
	def __init__(self,id=None,graph=None,data=None):
		self.id = id
		self.graph = graph
		self.connections = GraphConnections(self)
		self._data = data
		self._cache = {}
		
	def __getattr__(self, property):
		if property.startswith('_'): return object.__getattr__(self,property)
		if property in self._cache:
			return self._cache[property]
		
		if not self._data: self._data = self._getObjectData(self.id)
		
		def handler(default=None):
			return self._data.get(property) or default
			
		handler.method = property
		
		self._cache[property] = handler
		return handler
	
	def _getObjectData(self,id,**args):
		fail = False
		try:
			return self.graph.get_object(id,**args)
		except GraphAPIError,e:
			if not e.type == 'OAuthException': raise
			fail = True
			
		if fail:
			print "ERROR GETTING OBJECT - GETTING NEW TOKEN"
			if not self.graph.getNewToken():
				if self.graph.access_token: raise GraphWrapAuthError('RENEW_TOKEN_FAILURE','Failed to get new token')
				else: return None
			return self.graph.get_object(id,**args)
		
class GraphData:
	def __init__(self,graphObject,data=None):
		self.graphObject = graphObject
		self.graph = self.graphObject.graph
		
	
	def __getattr__(self, property):
		if property.startswith('_'): return object.__getattr__(self,property)
		if property in self._cache:
			return self._cache[property]
		
		if not self._data: self._data = self._getObjectData(self.graphObject.id)
		
		def handler(default=None):
			return self._data.get(property,default)
			
		handler.method = property
		
		self._cache[property] = handler
		return handler
	
	def _getObjectData(self,id,**args):
		fail = False
		try:
			return self.graph.get_object(id,**args)
		except GraphAPIError,e:
			if not e.type == 'OAuthException': raise
			fail = True
			
		if fail:
			print "ERROR GETTING OBJECT - GETTING NEW TOKEN"
			if not self.graph.getNewToken():
				if self.graph.access_token: raise GraphWrapAuthError('RENEW_TOKEN_FAILURE','Failed to get new token')
				else: return None
			return self.graph.get_object(id,**args)
	
class GraphConnections:
	def __init__(self,graphObject):
		self.graphObject = graphObject
		self.graph = self.graphObject.graph
		self.cache = {}
		
	def __getattr__(self, method):
		if method.startswith('_'): return object.__getattr__(self,method)
		if method in self.cache:
			return self.cache[method]
				
		def handler(paging=True,**args):
			fail = False
			try:
				connections = self.graph.get_connections(self.graphObject.id, method.replace('__','/'), **args)
				return self._processConnections(connections,paging)
			except GraphAPIError,e:
				print e.type
				if not e.type == 'OAuthException': raise
				fail = True
	
			if fail:
				print "ERROR GETTING CONNECTIONS - GETTING NEW TOKEN"
				if not self.graph.getNewToken():
					if self.graph.access_token: raise GraphWrapAuthError('RENEW_TOKEN_FAILURE','Failed to get new token')
					else: return None
				connections =  self.graph.get_connections(self.graphObject.id, method.replace('__','/'), **args)
				return self._processConnections(connections,paging)
			
		handler.method = method
		
		self.cache[method] = handler
		return handler
	
	def _processConnections(self,connections,paging):
		return self.graph._processConnections(connections,paging)
			
class GraphWrap(GraphAPI):
	def __init__(self,token,new_token_callback=None):
		GraphAPI.__init__(self,token)
		self.uid = None
		self._newTokenCallback = new_token_callback
	
	def getObject(self,id):
		return GraphObject(id,self)
	
	def getObjects(self,ids=[]):
		data = self.get_objects(ids)
		objects = {}
		for id in data:
			objects[id] = GraphObject(id,self,data[id])
		return objects
		
	def urlRequest(self,url,paging=True):
		connections = self.request(url)
		return self._processConnections(connections, paging)
		
	def _processConnections(self,connections,paging):
		cons = []
		for c in connections['data']:
			cons.append(GraphObject(c['id'],self,c))
		if not paging: return cons
		next,prev = self._getPaging(connections)
		return cons,next,prev

	def _getPaging(self,obj):
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
	
	def areAlmostTheSame(self,first,second):
		if not first or not second: return False
		first = re.sub('(\d{4}-\d{2}-\d{2}T\d{2}%3A\d{2}%3A\d)\d(%2B\d{4})',r'\1x\2',first)
		second = re.sub('(\d{4}-\d{2}-\d{2}T\d{2}%3A\d{2}%3A\d)\d(%2B\d{4})',r'\1x\2',second)
		return first == second
	
	def setLogin(self,email,passw,uid=None,token=None):
		self.uid = uid
		self.login_email = email
		self.login_pass = passw
		if token: self.access_token = token
		
	def setAppData(self,aid,redirect='http://www.facebook.com/connect/login_success.html',scope=None):
		self.client_id = aid
		self.redirect = redirect
		self.scope = scope
		
	def checkHasPermission(self,permission):
		url = 'https://api.facebook.com/method/users.hasAppPermission?format=json&ext_perm='+permission+'&access_token='+self.access_token
		fobj = urllib.urlopen(url)
		try:
			response = _parse_json(fobj.read())
		finally:
			fobj.close()
		return (response == 1)
		
	def checkIsAppUser(self):
		url = 'https://api.facebook.com/method/users.isAppUser?format=json&access_token='+self.access_token
		fobj = urllib.urlopen(url)
		try:
			response = _parse_json(fobj.read())
		finally:
			fobj.close()
		return response
			
	def getNewToken(self):
		import mechanize #@UnresolvedImport
		br = mechanize.Browser()
		br.set_handle_robots(False)
		scope = ''
		if self.scope: scope = '&scope=' + self.scope
		url = 	'https://www.facebook.com/dialog/oauth?client_id='+self.client_id+\
				'&redirect_uri='+self.redirect+\
				'&type=user_agent&display=popup'+scope
		print url
		try:
			res = br.open(url)
			html = res.read()
		except:
			print "ERROR: TOKEN PAGE INITIAL READ"
			raise
		
		script = False
		try:
			#check for login form
			br.select_form(nr=0)
			print "HTML"
		except:
			self.genericError()
			script = True
			print "SCRIPT"
			
		if script:
			#no form, maybe we're logged in and the token is in javascript on the page
			token = self.parseTokenFromScript(html)
		else:
			try:
				#fill out the form and submit
				br['email'] = self.login_email
				br['pass'] = self.login_pass
				res = br.submit()
				url = res.geturl()
				print "FORM"
			except:
				print "FORM ERROR"
				raise
				
			script = False
			token = self.extractTokenFromURL(url)
			if not token: script = True
			
			if script:
				print "SCRIPT TOKEN"
				#no token in the url, let's try to parse it from javascript on the page
				html = res.read()
				print html
				token = self.parseTokenFromScript(html)
				token = urllib.unquote(token.decode('unicode-escape'))
		
		if not self.tokenIsValid(token):
			#if script: LOG("HTML:" + html)
			return False
		print "|--------------------"
		print "|TOKEN: %s" % token
		print "|--------------------"
		self.saveToken(token)
		return token
		
	def extractTokenFromURL(self,url):
		try:
			#we submitted the form, check the result url for the access token
			from cgi import parse_qs
			import urlparse
			token = parse_qs(urlparse.urlparse(url.replace('#','?',1))[4])['access_token'][0]
			print "URL TOKEN: %s" % token
			return token
		except:
			print "TOKEN URL: %s" % url
			self.genericError()
			return None
		
	def tokenIsValid(self,token):
		if not token: return False
		if 'login_form' in token and 'standard_explanation' in token:
			reason = re.findall('id="standard_explanation">(?:<p>)?([^<]*)<',token)
			if reason: print reason[0]
			print "TOKEN: " + token
			raise GraphWrapAuthError('LOGIN_FAILURE',reason)
			return False
		if 'html' in token or 'script' in token or len(token) > 160:
			print "TOKEN: " + token
			raise GraphWrapAuthError('RENEW_TOKEN_FAILURE','Failed to get new token')
			return False
		return True
		
	def genericError(self):
		print 'ERROR: %s::%s (%d) - %s' % (self.__class__.__name__
								   , sys.exc_info()[2].tb_frame.f_code.co_name, sys.exc_info()[2].tb_lineno, sys.exc_info()[1])
								
	def parseTokenFromScript(self,html):
		return urllib.unquote_plus(html.split("#access_token=")[-1].split("&expires")[0])
		
	def saveToken(self,token=None):
		if token:
			self.access_token = token
			if self._newTokenCallback: self._newTokenCallback(token)