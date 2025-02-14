// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

var setActiveClass = function(el) {
  el.classList.add('active')
}

var removeActiveClass = function(el) {
  el.classList.remove('active')
}

var setUpHoverEffect = function (triggerElementId, effectedEl) {
  var triggerEl = document.getElementById(triggerElementId);
  triggerEl.addEventListener('mouseover', function() {
      setActiveClass(effectedEl)
  })
      triggerEl.addEventListener('mouseout', function() {
      removeActiveClass(effectedEl)
  })
}

//* MODAL LOGIC *//
var toggleModal = function (userId) {
  var e = window.event
  e.stopPropagation()

  var aboutBackdrop = document.getElementById('about-backdrop')
  var aboutModal = document.getElementById('about-modal')

  if(aboutModal.classList.contains('modal-active') && aboutBackdrop.classList.contains('modal-active')) {
      aboutBackdrop.classList.remove('modal-active')
      aboutModal.classList.remove('modal-active')
      document.body.classList.remove('no-scroll')
  } else if(userId){
      aboutBackdrop.classList.add('modal-active')
      aboutModal.classList.add('modal-active')
      document.body.classList.add('no-scroll')
  }

  var modals = [].slice.call(document.getElementsByClassName('about-modal-inner'))

  modals.forEach(function(el) {
      if(el.id && el.id ===( userId+'Modal')) {
          el.classList.add('modal-active')
      } else {
          el.classList.remove('modal-active')
      }
  })
}



window.addEventListener("load", function(){
  var viewBioButtons = [].slice.call(document.getElementsByClassName('hex-member-bio-button'));
  viewBioButtons.forEach(function(el){
    el.addEventListener('click', toggleModal.bind(null,el.id.substr(7).toLowerCase()))
  })

  var aboutBackdrop = document.getElementById('about-backdrop')
  var closeAboutModal = document.getElementById('close-about-modal')

  aboutBackdrop.addEventListener('click', toggleModal)
  closeAboutModal.addEventListener('click', toggleModal)

  /* TABLET & MOBILE LOGIC */
  var screenSize = window.innerWidth

  window.addEventListener('resize', function(){
    screenSize = window.innerWidth
  })

  var headshotContainers = [].slice.call(document.getElementsByClassName('hexIn'));
  headshotContainers.forEach(function(el){
    el.addEventListener('click', function() {
        if(screenSize < 767) {
            toggleModal(el.id.substr(0,el.id.length-2).toLowerCase())
        }
    })
  })
});
