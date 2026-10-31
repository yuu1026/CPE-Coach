# Local browser dependencies

CodeMirror 5.65.16: downloaded from https://registry.npmjs.org/codemirror/-/codemirror-5.65.16.tgz . Includes core, C-like mode, matchBrackets and closeBrackets. MIT license retained in codemirror/LICENSE.

markdown-it 14.1.0: downloaded from https://registry.npmjs.org/markdown-it/-/markdown-it-14.1.0.tgz . MIT license retained in markdown-it/LICENSE. Renderer disables HTML, images and linkification. Text and code submitted by users remain escaped by Django; assistant Markdown is parsed with HTML disabled.

Assets are served from the local project. No CDN requests are made by the editor or chat renderer.
