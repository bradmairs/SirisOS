import 'dart:math' as math;

import 'package:flutter/material.dart';

class SirisLogo extends StatefulWidget {
  const SirisLogo({this.size = 56, this.showWordmark = true, super.key});

  final double size;
  final bool showWordmark;

  @override
  State<SirisLogo> createState() => _SirisLogoState();
}

class _SirisLogoState extends State<SirisLogo>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 7),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final mark = RepaintBoundary(
      child: SizedBox.square(
        dimension: widget.size,
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) => CustomPaint(
            painter: _SirisMarkPainter(progress: _controller.value),
          ),
        ),
      ),
    );

    if (!widget.showWordmark) return mark;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        mark,
        SizedBox(height: widget.size * 0.17),
        ShaderMask(
          blendMode: BlendMode.srcIn,
          shaderCallback: (bounds) => const LinearGradient(
            colors: [
              Color(0xFFFFFFFF),
              Color(0xFFD6D6D8),
              Color(0xFFFF2638),
            ],
          ).createShader(bounds),
          child: Text(
            'SIRISOS',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 3.2,
                  height: 1,
                ),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          'YOUR PERSONAL OS',
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: const Color(0xFF8C8D93),
                fontWeight: FontWeight.w600,
                letterSpacing: 1.45,
              ),
        ),
      ],
    );
  }
}

class _SirisMarkPainter extends CustomPainter {
  const _SirisMarkPainter({required this.progress});

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final centre = size.center(Offset.zero);
    final shortest = size.shortestSide;
    final rect = Offset.zero & size;

    final haloPaint = Paint()
      ..shader = RadialGradient(
        colors: [
          const Color(0xFFFF2034).withValues(alpha: 0.30),
          const Color(0xFF7A0710).withValues(alpha: 0.14),
          Colors.transparent,
        ],
        stops: const [0, 0.58, 1],
      ).createShader(rect)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, shortest * 0.09);
    canvas.drawCircle(centre, shortest * 0.49, haloPaint);

    final shellRect = Rect.fromCircle(center: centre, radius: shortest * 0.43);
    final shellPaint = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFF2A0B10), Color(0xFF0B0B0E), Color(0xFF020203)],
      ).createShader(shellRect);
    canvas.drawCircle(centre, shortest * 0.43, shellPaint);

    final ringPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = shortest * 0.018
      ..shader = SweepGradient(
        transform: GradientRotation(progress * math.pi * 2),
        colors: const [
          Color(0x00FF2436),
          Color(0xFFFF2638),
          Color(0xFF8B0B16),
          Color(0x00FF2436),
        ],
        stops: const [0, 0.28, 0.62, 1],
      ).createShader(shellRect);
    canvas.drawArc(
      shellRect.deflate(shortest * 0.018),
      -math.pi * 0.72,
      math.pi * 1.48,
      false,
      ringPaint,
    );

    final ribbon = Path()
      ..moveTo(shortest * 0.72, shortest * 0.25)
      ..cubicTo(
        shortest * 0.55,
        shortest * 0.13,
        shortest * 0.25,
        shortest * 0.20,
        shortest * 0.27,
        shortest * 0.39,
      )
      ..cubicTo(
        shortest * 0.29,
        shortest * 0.51,
        shortest * 0.52,
        shortest * 0.51,
        shortest * 0.64,
        shortest * 0.61,
      )
      ..cubicTo(
        shortest * 0.79,
        shortest * 0.74,
        shortest * 0.56,
        shortest * 0.89,
        shortest * 0.30,
        shortest * 0.78,
      );

    final glowPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = shortest * 0.17
      ..color = const Color(0xFFFF182D).withValues(alpha: 0.30)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, shortest * 0.10);
    canvas.drawPath(ribbon, glowPaint);

    final ribbonPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = shortest * 0.108
      ..shader = const LinearGradient(
        begin: Alignment.topRight,
        end: Alignment.bottomLeft,
        colors: [
          Color(0xFFFFA3AA),
          Color(0xFFFF2438),
          Color(0xFF8D0B15),
          Color(0xFF240408),
        ],
        stops: [0, 0.30, 0.66, 1],
      ).createShader(rect);
    canvas.drawPath(ribbon, ribbonPaint);

    final innerRibbonPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = shortest * 0.040
      ..shader = const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [Color(0xFFFFFFFF), Color(0xFF8D9097), Color(0xFF16171B)],
      ).createShader(rect);
    canvas.drawPath(ribbon, innerRibbonPaint);

    final highlightPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = shortest * 0.017
      ..shader = LinearGradient(
        colors: [
          Colors.white.withValues(alpha: 0.95),
          const Color(0xFFFFC3C8).withValues(alpha: 0.48),
          Colors.transparent,
        ],
      ).createShader(rect);
    canvas.drawPath(ribbon, highlightPaint);

    final orbitRadius = shortest * 0.405;
    final dotPaint = Paint();
    for (var index = 0; index < 6; index++) {
      final angle = progress * math.pi * 2 + index * (math.pi * 2 / 6);
      final pulse = 0.65 + 0.35 * math.sin(angle * 2.3);
      final dot = Offset(
        centre.dx + math.cos(angle) * orbitRadius,
        centre.dy + math.sin(angle) * orbitRadius,
      );
      dotPaint.color = const Color(0xFFFF4554).withValues(alpha: pulse);
      dotPaint.maskFilter = MaskFilter.blur(BlurStyle.normal, shortest * 0.014);
      canvas.drawCircle(dot, shortest * (0.011 + 0.005 * pulse), dotPaint);
    }

    final corePaint = Paint()
      ..color = const Color(0xFFFFF2F3).withValues(alpha: 0.90)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, shortest * 0.025);
    canvas.drawCircle(
      Offset(shortest * 0.72, shortest * 0.25),
      shortest * 0.018,
      corePaint,
    );
  }

  @override
  bool shouldRepaint(covariant _SirisMarkPainter oldDelegate) =>
      oldDelegate.progress != progress;
}
