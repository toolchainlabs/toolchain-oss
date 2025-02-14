// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/* TOGGLE MENU */

var toggleMenu = function () {
    var backdrop = document.getElementById('menu-backdrop')
    var menu = document.getElementById('mobile-menu')

    if(menu.classList.contains('menu-active') && backdrop.classList.contains('menu-active')) {
        menu.classList.remove('menu-active')
        backdrop.classList.remove('menu-active')
        document.body.classList.remove('no-scroll')
    } else {
        menu.classList.add('menu-active')
        backdrop.classList.add('menu-active')
        document.body.classList.add('no-scroll')
    }
}

var hamburgerMenuButton = document.getElementById('hamb-menu-button')
var closeMenuButton = document.getElementById('close-menu-button')
var backdrop = document.getElementById('menu-backdrop')

hamburgerMenuButton.addEventListener('click', toggleMenu)
closeMenuButton.addEventListener('click', toggleMenu)
backdrop.addEventListener('click', toggleMenu)

/* DETECT FINGER SWIPE */

var xDown = null;

function getTouches(e) {
    return e.touches || e.originalEvent.touches
}

function handleTouchStart(e) {
    const firstTouch = getTouches(e)[0];
    xDown = firstTouch.clientX;
}

function handleTouchMove(e) {
    if ( !xDown ) {
        return null;
    }

    var xUp = e.touches[0].clientX;

    var xDiff = xDown - xUp;

    var menu = document.getElementById('mobile-menu')
    var isMenuActive = menu.classList.contains('menu-active')

    if(xDiff>10 && isMenuActive) {
        toggleMenu()
    }

    xDown = null;
}

document.addEventListener('touchstart', handleTouchStart, false);        
document.addEventListener('touchmove', handleTouchMove, false);