/* =====================================================
   GLOBAL 3D MOUSE TILT EFFECT
   ===================================================== */

const elements = document.querySelectorAll(
    ".service-card, " +
    ".step, " +
    ".dashboard-card, " +
    ".stat-card, " +
    ".info-card, " +
    ".booking-card, " +
    ".profile-card, " +
    ".request-card, " +
    ".status-card"
);

elements.forEach((element) => {

    element.addEventListener("mousemove", (event) => {

        const rect = element.getBoundingClientRect();

        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        const rotateY = ((x - centerX) / centerX) * 7;
        const rotateX = ((centerY - y) / centerY) * 7;

        element.style.transform =
            `perspective(1000px)
             rotateX(${rotateX}deg)
             rotateY(${rotateY}deg)
             translateY(-8px)`;
    });


    element.addEventListener("mouseleave", () => {

        element.style.transform =
            "perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)";

    });

});