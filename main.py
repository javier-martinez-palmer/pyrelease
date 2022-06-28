import mechanize
import urllib

br = mechanize.Browser()
br.set_handle_robots(False)
br.set_handle_equiv(False)
br.set_handle_refresh(False)
br.addheaders = [('User-agent', 'Mozilla/5.0')] 

url = 'https://javier-martinez-palmer.github.io/pyrelease/'
br.open(url, timeout=10.0)

print([str(i) for i in br.forms()])
# If exist any form
#br.select_form(nr= 0)#"ReleaseForm")#
br.select_form(ls_form='release-init')
#br.form['ReleaseForm']=str('new-task-btn')
print(br)
#br.form.set(True, '', 'github_token')
br.form['github_token']=''
print(br)
br.form.find_control(name="download-release").selected = False
print(br)
br.form.find_control(name="do-release").selected = True
print(br)
br.form.find_control(name="version-release").selected = True
print(br)
#br.form["version-module"]= ['version-blender']
# click on the button and saved it into a variable
#data = br.submit()
#print(data.info())
print(urllib.request.urlopen(br.form.click()).read())