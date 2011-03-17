boxee.browserWidth=1280;
boxee.browserHeight=720;

boxee.enableLog(true);
boxee.renderBrowser=true;
boxee.autoChoosePlayer=false;

boxee.setMode(boxee.BROWSER_MODE);
boxee.log('set to browser mode');

requestedURL = boxee.getParam("src");
userEmail = boxee.getParam("email");
userPass = boxee.getParam("password");
boxee.log(requestedURL);
boxee.log(userEmail);

var lastLocation;
var authCheckTimer;

checkForms = function(){
	browser.execute(
		'var formsArray = document.getElementsByTagName("form");' +
		'var tesT;' +
		'for (i=0; i<formsArray.length; i++){' +
			'form = formsArray[i];' +
			'action = form.getAttribute("action");' +
			'if(action.indexOf("login.php") != -1){' +
				'for (i=0; i < form.elements.length; i++){' +
					'element = form.elements[i];' +
					'if(element.name == "email"){' +
						'element.value = "' + userEmail + '";' +
					'}' +
					'if(element.name == "pass"){' +
						'element.value = "' + userPass + '";' +
					'}' +
				'}' +
				'form.submit();' +
			'}' +
			'if(action.indexOf("uiserver.php") != -1){' +
				'for (i=0; i < form.elements.length; i++){' +
					'element = form.elements[i];' +
					'if(element.name == "grant_clicked"){' +
						'element.click();' +
					'}' +
				'}' +
			'}' +
		'}'
	);
}

processPage = function(){
	loc = browser.getLocation();
	if(loc.indexOf('#access_token') != -1){
		boxee.log('FBAUTH - AUTHORIZATION SUCCESS');
		doExit();
	}else{
		checkForms();
	}	
}

doExit = function(){
	boxee.log('FB AUTH - EXITED AT: ' + loc)
	cancelInterval(authCheckTimer);
	boxee.notifyPlaybackEnded();	
}

boxee.onDocumentLoaded = function(){
	authCheckTimer = setInterval(
		function(){
			loc = browser.getLocation();
			if(loc != lastLocation){
				lastLocation = loc;
				boxee.log('FBAUTH - PAGE CHANGE DETECTED');
				processPage();
			}
		}
		,500
	);
	boxee.log('FBAUTH - onDocumentLoaded');
	processPage();
}

boxee.onEnter = function(){
	boxee.log('FBAUTH - onEnter');
    processPage();
}


boxee.onBack = function() {
	doExit();
}