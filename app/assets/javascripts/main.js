window.GOVUK.Frontend.initAll();

var showHideContent = new GOVUK.ShowHideContent();
showHideContent.init();

$(() => GOVUK.modules.start());

$(() => $('.error-message, .usa-error-message').eq(0).parent('label').next('input').trigger('focus'));


// Applies our expanded focus style to the siblings of links when that link is wrapped in a heading.
//
// This will be possible in CSS in the future, using the :has pseudo-class. When :has is available
// in the browsers we support, this code can be replaced with a CSS-only solution.
$('.js-mark-focus-on-parent').on('focus blur', '*', e => {
  $target = $(e.target);
  if (e.type === 'focusin') {
    $target.parent().addClass('js-child-has-focus');
  } else {
    $target.parent().removeClass('js-child-has-focus');
  }
});
