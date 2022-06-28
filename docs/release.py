#!/usr/bin/python3

#TODO: REPLACE BY A GIT-WORKFLOW
'''
# https://gist.github.com/tomac4t/16dc1e91d95c94f60251e586672b6314
name: release assets
on:
  release:
    types: [created]
jobs:
  debiab-buster:
    runs-on: ubuntu-latest
    container: debian:buster
    env: 
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      GH_REPO: ${{ github.repository }}
      GH_REF: ${{ github.ref }}
    steps:
    - name: upgrade the packages
      run: apt-get update && apt-get upgrade -y && apt-get install -y git 
    - uses: actions/checkout@v2
    - name: build
      run: .github/workflows/release-debian-package.sh
    - name: upload the assets
      run: .github/workflows/release-assets-upload.py
'''


import os
import json
import base64
import shutil
import configparser

import js
from pyodide.http import pyfetch
from pyodide import JsException


GIT_SERVICE = 'https://github.com/' #'https://github.int.midasplayer.com/'

async def list_files(root_folder='/'):
    ret = []
    for subdir, dirs, files in os.walk(root_folder):
        for file in files:
            ret.append(os.path.join(subdir, file))
    return ret


async def download(url, filename):
    try:
        response = await pyfetch(url)
        if response.ok:
            with open(filename, mode="wb") as file:
                file.write(await response.bytes())
    except JsException:
        return None
    else:
        return filename


async def get_owner_repo():
    url = js.window.location.href
    url = url.replace(GIT_SERVICE,'')
    url = url.replace('/docs/index.html','')
    url = url.split('/')
    return url[0], url[1]


async def image_load_show():
    filename = await loop.run_until_complete(
        download("https://placekitten.com/500/900", "cats.jpg")
    )

    data = base64.b64encode(open(filename, "rb").read()).decode("utf-8")
    src = f"data:image/jpeg;charset=utf-8;base64,{data}"
    js.document.querySelector("img").setAttribute("src", src)


async def find_default_branch(repo_owner, repo_name, github_token):
    repo = 'main'
    headers = {'Authorization': f'token {github_token}'}
    url = f'{GIT_SERVICE}/api/v3/repos/{repo_owner}/{repo_name}'
    response = await pyfetch(url, metrod='GET', headers=headers)
    if response.ok:
        repo = await response.json()
        return repo['default_branch']
    return repo

def handler(func, path, exc_info):
    fixes=False
    for root, dirs, files in os.walk(path):
        for i in files:
            filepath=os.path.join(root, i)
            os.remove(filepath)
            fixes=True
    if fixes:
        func(path)

async def files_get(folder_path, repo_owner, repo_name, repo_branch, github_token):
    headers = {'Authorization': f'token {github_token}'}
    url = f'{GIT_SERVICE}api/v3/repos/{repo_owner}/{repo_name}/git/trees/{repo_branch}?recursive=1'
    # TODO: why shutil.rmtree dont work here?
    # No files and no folder is removed
    # Besides, even if folder is empty (using os.remove) os.rmdir doesnt 
    # remove the folder
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path, onerror=handler)
    else:
        os.makedirs(folder_path)
    response = await pyfetch(url, metrod='GET', headers=headers)
    repo = await response.json()
    submodules = []
    for i in repo['tree']:
        if not any(subfolder in i['path'] for subfolder in ['docs/','test/']):
            if i['type'] == 'blob':
                filename = os.path.join(folder_path, i['path'])
                response = await pyfetch(i['url'], method='GET', headers=headers)
                if response.ok:
                    binblob = await response.json()
                    with open(filename, mode="wb") as file:
                        file.write(base64.b64decode(binblob['content']))#await response.bytes())#bytes(binblob['content']))#(await response.bytes())
            elif i['type'] == 'tree':
                os.makedirs(os.path.join(folder_path, i['path']))
            elif i['type']=='commit':
                submodules.append(i)
    # test read back the files
    filename = os.path.join(folder_path,'.gitmodules')
    if os.path.exists(filename):
        config = configparser.ConfigParser(allow_no_value=True)
        config.read_file(open(filename))
        for sec in config.sections():
            aux = config[sec]['url'].split('/')
            _owner = aux[-2]
            _name = aux[-1].replace('.git','')
            _branch = await find_default_branch(_owner, _name, github_token)
            await files_get(os.path.join(folder_path, config[sec]['path']), _owner, _name, _branch, github_token)
                

def zip_repo(folder_path='/home/repo/', zip_name='/home/repo/folder.zip'):
    shutil.make_archive(zip_name.replace('.zip',''), 'zip', folder_path, '.')


def get_version_from_init_blender(folder_path):
    version = '0.0.0'
    with open(os.path.join(folder_path, '__init__.py'), 'r') as f:
        for l in f.readlines():
            aux = ''.join(l.split())
            if aux.startswith('''"version":'''):
                _, version = aux.split('(')
                version, _ = version.split(')')
                version = version.replace(',','.')
                break
    with open(os.path.join(folder_path, 'VERSION'), 'w') as f:
        f.write(version)
    return version

def get_version_from_init_module(folder_path):
    version = '0.0.0'
    with open(os.path.join(folder_path, '__init__.py'), 'r') as f:
        for l in f.readlines():
            aux = ''.join(l.split())
            if aux.startswith('''__version__'''):
                _, version,_ = aux.split('"')
                break
    with open(os.path.join(folder_path, 'VERSION'), 'w') as f:
        f.write(version)
    return version


async def release_create(blob, filename, repo_version, repo_owner, repo_name, repo_branch, github_token):
    # create release
    repo = None
    url =  f'{GIT_SERVICE}api/v3/repos/{repo_owner}/{repo_name}/releases'
    headers = {'Authorization': f'token {github_token}',"Accept": "application/vnd.github.v3+json"}
    body = json.dumps({"tag_name": f'v{repo_version}', "target_commitish": f"{repo_branch}", "name":f"v{repo_version}", "body":"Description of the release", "draft":False, "prerelease":False})
    response = await pyfetch(url, method='POST', headers=headers, body=body)
    if response.ok:
        repo = await response.json()
    else:
        # in case it existed the response is invalid, so we need to get it
        repo = None
        url =  f'{GIT_SERVICE}api/v3/repos/{repo_owner}/{repo_name}/releases/tags/v{repo_version}'
        headers = {'Authorization': f'token {github_token}',"Accept": "application/vnd.github.v3+json"}
        response = await pyfetch(url, method='GET', headers=headers)
        repo = await response.json()

    # upload asset
    url = repo['upload_url']
    url = url.replace(u'{?name,label}','')
    url = url+f'?name={os.path.basename(filename)}'
    headers = {'Authorization': f'token {github_token}', "Content-Type": "application/octet-stream"}#, "Content-Length": f'{len(data)}'} #
    response = await pyfetch(url, method='POST', headers=headers, body=blob) #data=data) ##params=params, 
    return



async def do_release(*ags, **kws):
    pyscript.write("console-green", 'RELEASE START', append=True)
    # get files
    folder_path = '/home/repo/'
    github_token = Element('github_token').element.value
    print (github_token)
    #repo_owner, repo_name = await get_owner_repo()
    repo_owner, repo_name = ('javier-martinez', 'ashura')
    repo_branch = await find_default_branch(repo_owner, repo_name, github_token)
    await files_get(folder_path, repo_owner, repo_name, repo_branch, github_token)
    
    # zip
    if Element('version-blender').element.checked:
        repo_version = get_version_from_init_blender(folder_path)
    elif Element('version-module').element.checked:
        repo_version = get_version_from_init_module(folder_path)
    zip_name=f'/home/{repo_name}-{repo_version}.zip'
    zip_repo(folder_path=folder_path, zip_name=zip_name)
    dfiles = await list_files('/home')
    print(str(dfiles))

    # create the blob-zip
    data = None
    with open(zip_name, 'rb') as f:
        data = f.read()
    array_buf = js.Uint8Array.new(data)
    blob = js.Blob.new([array_buf], {type: 'application/zip'})

    # create release uploading blob-zip
    if Element('do-release').element.checked:
        await release_create(blob, zip_name, repo_version, repo_owner, repo_name, repo_branch, github_token)
        pyscript.write("console-green", f'release {repo_version} created!', append=True)

    # download blob-zip
    if Element('download-release').element.checked:
        url = js.window.URL.createObjectURL(blob)
        pyscript.write("console-green", f'download {repo_version} ready to start', append=True)
        #js.window.location.assign(url)
        bdown = js.document.createElement('a')
        bdown.href = url
        bdown.target = '_blank'
        bdown.download = os.path.basename(zip_name)
        js.document.body.appendChild(bdown)
        bdown.click()
        js.document.body.removeChild(bdown)

    pyscript.write("console-green", 'RELEASE DONE', append=True)
    
