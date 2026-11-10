function drawSpecimen(g, size, angle, phase, color, dead = false) {
  g.save();
  g.rotate(angle);
  g.scale(size, size);
  g.lineCap = "round";
  g.lineJoin = "round";
  g.shadowColor = "#000";
  g.shadowBlur = 7;
  g.shadowOffsetY = 2;
  for (let side of [-1, 1])
    for (let j = 0; j < 3; j++) {
      const gait = dead ? 0 : Math.sin(phase + j * 2 + side) * 0.1;
      g.beginPath();
      g.moveTo(0.12 - j * 0.2, side * 0.12);
      g.lineTo(0.45 - j * 0.42 + gait, side * (0.4 + j * 0.02));
      g.lineTo(0.68 - j * 0.64, side * (0.65 + gait));
      g.strokeStyle = "#b39972";
      g.lineWidth = 0.033;
      g.stroke();
      g.beginPath();
      g.moveTo(0.68 - j * 0.64, side * (0.65 + gait));
      g.lineTo(0.8 - j * 0.7, side * (0.7 + gait));
      g.lineWidth = 0.016;
      g.stroke();
    }
  g.shadowBlur = 0;
  g.shadowOffsetY = 0;
  const body = g.createLinearGradient(0, -0.3, 0, 0.3);
  body.addColorStop(0, "#44301e");
  body.addColorStop(0.35, "#dab77b");
  body.addColorStop(0.6, "#aa804d");
  body.addColorStop(1, "#3b2b20");
  g.fillStyle = body;
  g.beginPath();
  g.ellipse(-0.4, 0, 0.65, 0.28, 0, 0, Math.PI * 2);
  g.fill();
  g.save();
  g.beginPath();
  g.ellipse(-0.4, 0, 0.65, 0.28, 0, 0, Math.PI * 2);
  g.clip();
  for (let j = 0; j < 6; j++) {
    g.beginPath();
    g.ellipse(-0.05 - j * 0.17, 0, 0.1, 0.32, 0, Math.PI * 0.5, Math.PI * 1.5);
    g.strokeStyle = "#3b281dc9";
    g.lineWidth = 0.06;
    g.stroke();
  }
  g.restore();
  g.fillStyle = body;
  g.beginPath();
  g.ellipse(0.17, 0, 0.32, 0.25, 0, 0, Math.PI * 2);
  g.fill();
  for (let side of [-1, 1]) {
    g.save();
    g.translate(0.02, side * 0.09);
    g.rotate(side * (0.35 + (dead ? 0 : Math.sin(phase * 3) * 0.035)));
    const wing = g.createLinearGradient(-1, 0, 0.3, side * 0.4);
    wing.addColorStop(0, "#b2c6d522");
    wing.addColorStop(0.5, "#d7e6eb66");
    wing.addColorStop(1, "#f3f6ec88");
    g.fillStyle = wing;
    g.strokeStyle = "#c7d7df99";
    g.lineWidth = 0.015;
    g.beginPath();
    g.moveTo(0.2, 0);
    g.bezierCurveTo(-0.2, side * 0.08, -1.25, side * 0.62, -1.37, side * 0.35);
    g.bezierCurveTo(-1.5, side * 0.07, -0.6, -side * 0.13, 0.2, 0);
    g.fill();
    g.stroke();
    for (let j = 0; j < 4; j++) {
      g.beginPath();
      g.moveTo(0.15, 0);
      g.quadraticCurveTo(
        -0.6,
        side * (0.05 + j * 0.07),
        -1.2 + j * 0.08,
        side * (0.12 + j * 0.07),
      );
      g.strokeStyle = "#7694a577";
      g.lineWidth = 0.012;
      g.stroke();
    }
    g.restore();
  }
  g.fillStyle = "#a28251";
  g.beginPath();
  g.ellipse(0.48, 0, 0.19, 0.21, 0, 0, Math.PI * 2);
  g.fill();
  for (let side of [-1, 1]) {
    const eye = g.createRadialGradient(
      0.5,
      side * 0.13,
      0.01,
      0.5,
      side * 0.14,
      0.13,
    );
    eye.addColorStop(0, "#f49675");
    eye.addColorStop(0.45, "#bc4e39");
    eye.addColorStop(1, "#57261f");
    g.fillStyle = eye;
    g.beginPath();
    g.ellipse(0.5, side * 0.16, 0.12, 0.1, side * 0.2, 0, Math.PI * 2);
    g.fill();
    g.strokeStyle = "#d3ad7b";
    g.lineWidth = 0.015;
    g.beginPath();
    g.moveTo(0.6, side * 0.05);
    g.quadraticCurveTo(0.8, side * 0.12, 0.82, side * 0.2);
    g.stroke();
  }
  g.fillStyle = color;
  g.beginPath();
  g.arc(0.16, 0, 0.055, 0, Math.PI * 2);
  g.fill();
  g.restore();
}
