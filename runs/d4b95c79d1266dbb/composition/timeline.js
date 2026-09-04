const tl = gsap.timeline({ paused: true });

tl.fromTo("#s1_background", {opacity: 0.94}, {opacity: 1, duration: 2.0, ease: "sine.inOut", repeat: 1, yoyo: true}, 0.0);
tl.fromTo("#s1_image", {objectPosition: "50% 50%"}, {objectPosition: "54% 50%", duration: 4.0, ease: "none"}, 0.0);
tl.fromTo("#s1_headline", {opacity: 0, clipPath: "inset(0 100% 0 0)"}, {opacity: 1, clipPath: "inset(0 0% 0 0)", duration: 0.75, ease: "power3.out"}, 0.09999999999999999);
tl.fromTo("#s1_text_2", {opacity: 0, y: 40}, {opacity: 1, y: 0, duration: 0.65, ease: "power3.out"}, 0.8999999999999999);
tl.fromTo("#s1_text_3", {opacity: 0, y: 40}, {opacity: 1, y: 0, duration: 0.65, ease: "power3.out"}, 2.4000000000000004);
tl.fromTo("#s2_background", {opacity: 0.94}, {opacity: 1, duration: 2.0, ease: "sine.inOut", repeat: 1, yoyo: true}, 4.0);
tl.to("#s2_signal", {x: -12, duration: 4.000, ease: "sine.inOut", repeat: 1, yoyo: true}, 4.0);
tl.fromTo("#s2_accent", {opacity: 1, scaleX: 0.86}, {opacity: 1, scaleX: 1, duration: 0.45, ease: "power2.out"}, 3.95);
tl.fromTo("#s2_headline", {opacity: 0, clipPath: "inset(0 100% 0 0)"}, {opacity: 1, clipPath: "inset(0 0% 0 0)", duration: 0.7, ease: "power3.out"}, 4.05);
tl.fromTo("#s2_text_2", {opacity: 0, y: 40}, {opacity: 1, y: 0, duration: 0.65, ease: "power3.out"}, 4.8500000000000005);
tl.fromTo("#s2_text_3", {opacity: 0, y: 40}, {opacity: 1, y: 0, duration: 0.65, ease: "power3.out"}, 6.3500000000000005);
tl.fromTo("#s3_background", {opacity: 0.94}, {opacity: 1, duration: 2.0, ease: "sine.inOut", repeat: 1, yoyo: true}, 8.0);
tl.fromTo("#s3_header", {opacity: 0, y: 40}, {opacity: 1, y: 0, duration: 0.6, ease: "power3.out"}, 8.049999999999999);
tl.fromTo("#s3_card_1", {opacity: 0, scale: 0.85}, {opacity: 1, scale: 1, duration: 0.6, ease: "back.out(1.15)"}, 8.6);
tl.fromTo("#s3_card_2", {opacity: 0, scale: 0.85}, {opacity: 1, scale: 1, duration: 0.6, ease: "back.out(1.15)"}, 9.2);
tl.fromTo("#s3_card_3", {opacity: 0, scale: 0.85}, {opacity: 1, scale: 1, duration: 0.65, ease: "back.out(1.15)"}, 9.85);
tl.fromTo("#s4_background", {opacity: 0.94}, {opacity: 1, duration: 2.0, ease: "sine.inOut", repeat: 1, yoyo: true}, 12.0);
tl.fromTo("#s4_header", {opacity: 0, clipPath: "inset(0 100% 0 0)"}, {opacity: 1, clipPath: "inset(0 0% 0 0)", duration: 0.65, ease: "power3.out"}, 12.049999999999999);
tl.fromTo("#s4_stat_1", {opacity: 0, y: 40}, {opacity: 1, y: 0, duration: 0.7, ease: "power3.out"}, 12.799999999999999);
tl.fromTo("#s4_stat_2", {opacity: 0, y: 40}, {opacity: 1, y: 0, duration: 0.7, ease: "power3.out"}, 13.5);
tl.fromTo("#s4_stat_3", {opacity: 0, y: 40}, {opacity: 1, y: 0, duration: 0.8, ease: "power3.out"}, 14.799999999999999);
tl.fromTo("#s5_background", {opacity: 0.94}, {opacity: 1, duration: 2.0, ease: "sine.inOut", repeat: 1, yoyo: true}, 16.0);
tl.fromTo("#s5_headline", {opacity: 0, scale: 0.85}, {opacity: 1, scale: 1, duration: 0.75, ease: "back.out(1.15)"}, 16.099999999999998);
tl.fromTo("#s5_button", {opacity: 0, y: 40}, {opacity: 1, y: 0, duration: 0.7, ease: "power3.out"}, 17.0);

window.__timelines["main"] = tl;