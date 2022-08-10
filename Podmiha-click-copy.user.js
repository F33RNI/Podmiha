// ==UserScript==
// @name         Podmiha-click-copy
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Podmiha tampermonkey script
// @author       Fern Lane
// @match        *://*/*
// @grant        none
// ==/UserScript==

// Copy mode: 0 - entire element, 1 - word under cursor
const COPY_MODE = 1;


(function() {
    'use strict';

    // Mouse click on document
    document.addEventListener('click', function(e) {
        e = e || window.event;

		// Initialize text variable
        let textToCopy = "";

        // Copy mode 1 - copy word under cursor
        if (COPY_MODE === 1) {
            try {
                const word = getWordAtPoint(e.target, e.x, e.y);
                if (word != null && word.length > 1) {
                    textToCopy = word;
                }
            } catch (err) {
                console.error('Error selecting word under cursor!', err);
            }
        }

		// Copy mode 0 - copy entire element
        else {
            try {
                const target = e.target || e.srcElement;
                const text = target.textContent || target.innerText;
                if (text != null && text.length > 1) {
                    textToCopy = text;
                }
            } catch (err) {
                console.error('Error selecting text from element!', err);
            }
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
					range.expand("word");
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
