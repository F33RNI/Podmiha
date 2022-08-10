// ==UserScript==
// @name         Podmiha-click-copy
// @namespace    http://tampermonkey.net/
// @version      1.2
// @description  Podmiha tampermonkey script
// @author       Fern Lane
// @match        *://*/*
// @grant        none
// ==/UserScript==

// Set to true to automatically remove the following characters from text when copying
const REMOVE_CHARS = true;
const CHARS_TO_REMOVE = ['?', '.'];

// Set to true automatically remove spaces before and after selected text
const TRIM = true;

// Page custom CSS Style to make selection transparent
const HTML_STYLE = "<style> " +
    "::-moz-selection { \n" +
    "\tcolor: inherit; \n" +
    "\tbackground-color: transparent;\n" +
    "\t}\n" +
    "::selection { \n" +
    "\tcolor: inherit;\n" +
    "\tbackground-color: transparent; \n" +
    "\t}" +
    "</style>";


(function() {
    'use strict';

    // Add custom CSS to the head of the page
    document.getElementsByTagName('head')[0].innerHTML += HTML_STYLE;

    // Mouse click on document -> copy word
    document.addEventListener('click', function(e) {
        e = e || window.event;

		// Initialize text variable
        let textToCopy = "";

        // Get word under cursor
        try {
            const word = getWordAtPoint(e.target, e.x, e.y);
            if (word != null && word.length > 1) {
                textToCopy = word;
            }
        } catch (err) {
            console.error('Error selecting word under cursor!', err);
        }

		// Copy to clipboard
        try {
            if (textToCopy != null && textToCopy.length > 1) {
                copyTextToClipboard(textToCopy);
                //alert('Copied: ' + textToCopy);
            }
        } catch (err) {
            console.error('Error error copying text!', err);
        }
    }, false);

    // Mouse double click -> copy entire element text
    document.addEventListener('dblclick', function(e) {
        e = e || window.event;

		// Initialize text variable
        let textToCopy = "";

        // Get element text
        try {
            const target = e.target || e.srcElement;
            const text = target.textContent || target.innerText;
            if (text != null && text.length > 1) {
                textToCopy = text;
            }
        } catch (err) {
            console.error('Error selecting text from element!', err);
        }

		// Copy to clipboard
        try {
            if (textToCopy != null && textToCopy.length > 1) {
                copyTextToClipboard(textToCopy);
                //alert('Copied: ' + textToCopy);
            }
        } catch (err) {
            console.error('Error error copying text!', err);
        }
    }, false);

	/**
	* Copies test to clipboard
	*/
    function copyTextToClipboard(text) {
        // Remove chars
        if (REMOVE_CHARS) {
            for (let i = 0; i < CHARS_TO_REMOVE.length; i++) {
                text = text.replaceAll(CHARS_TO_REMOVE[i], '');
            }
        }

        // Trim
        if (TRIM) {
            text = text.trim();
        }

        // Copy to clipboard
        if (!navigator.clipboard) {
            fallbackCopyTextToClipboard(text);
            return;
        }
        navigator.clipboard.writeText(text).then(function() {
            console.log('Copying to clipboard was successful!');
        }, function(err) {
            console.error('Could not copy text: ', err);
        });
    }
	function fallbackCopyTextToClipboard(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.top = '0';
        textArea.style.left = '0';
        textArea.style.position = 'fixed';

        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        try {
            const successful = document.execCommand('copy');
            const msg = successful ? 'successful' : 'unsuccessful';
            console.log('Copying text command was ' + msg);
        } catch (err) {
            console.error('Unable to copy', err);
        }

        document.body.removeChild(textArea);
    }

	/**
	* Gets word at cursor position
    * https://stackoverflow.com/a/3710561/8163657
	*/
	function getWordAtPoint(elem, x, y) {
		let range;
        if (elem.nodeType === elem.TEXT_NODE) {
			range = elem.ownerDocument.createRange();
			range.selectNodeContents(elem);
            let currentPos = 0;
            const endPos = range.endOffset;
            while (currentPos+1 < endPos) {
				range.setStart(elem, currentPos);
				range.setEnd(elem, currentPos+1);
				if (range.getBoundingClientRect().left <= x && range.getBoundingClientRect().right >= x &&
				range.getBoundingClientRect().top <= y && range.getBoundingClientRect().bottom >= y) {
					range.expand('word');
                    const ret = range.toString();
                    range.detach();
					return(ret);
				}
				currentPos += 1;
			}
		} else {
			for (let i = 0; i < elem.childNodes.length; i++) {
                range = elem.childNodes[i].ownerDocument.createRange();
                range.selectNodeContents(elem.childNodes[i]);
				if(range.getBoundingClientRect().left <= x && range.getBoundingClientRect().right >= x &&
				range.getBoundingClientRect().top <= y && range.getBoundingClientRect().bottom >= y) {
					range.detach();
					return (getWordAtPoint(elem.childNodes[i], x, y));
				} else {
					range.detach();
				}
			}
		}
		return null;
	}
})();
