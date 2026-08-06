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
              Color(0xFFF8FBFF),
              Color(0xFFB9D7FF),
              Color(0xFF38D9FF),
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
                color: const Color(0xFF71869F),
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
          const Color(0xFF1ED8FF).withValues(alpha: 0.24),
          const Color(0xFF315BFF).withValues(alpha: 0.09),
          Colors.transparent,
        ],
        stops: const [0, 0.55, 1],
      ).createShader(rect)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, shortest * 0.08);
    canvas.drawCircle(centre, shortest * 0.48, haloPaint);

    final shellRect = Rect.fromCircle(center: centre, radius: shortest * 0.43);
    final shellPaint = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFF102A4A), Color(0xFF071321), Color(0xFF040A12)],
      ).createShader(shellRect);
    canvas.drawCircle(centre, shortest * 0.43, shellPaint);

    final ringPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = shortest * 0.018
      ..shader = SweepGradient(
        transform: GradientRotation(progress * math.pi * 2),
        colors: const [
          Color(0x001FD9FF),
          Color(0xFF1FD9FF),
          Color(0xFF376BFF),
          Color(0x001FD9FF),
        ],
        stops: const [0, 0.28, 0.58, 1],
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
      ..strokeWidth = shortest * 0.16
      ..color = const Color(0xFF168CFF).withValues(alpha: 0.26)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, shortest * 0.09);
    canvas.drawPath(ribbon, glowPaint);

    final ribbonPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = shortest * 0.105
      ..shader = const LinearGradient(
        begin: Alignment.topRight,
        end: Alignment.bottomLeft,
        colors: [
          Color(0xFF72F6FF),
          Color(0xFF12C8FF),
          Color(0xFF2764FF),
          Color(0xFF5532E9),
        ],
        stops: [0, 0.34, 0.68, 1],
      ).createShader(rect);
    canvas.drawPath(ribbon, ribbonPaint);

    final highlightPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = shortest * 0.022
      ..shader = LinearGradient(
        colors: [
          Colors.white.withValues(alpha: 0.88),
          const Color(0xFFB8F7FF).withValues(alpha: 0.42),
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
      dotPaint.color = const Color(0xFF65ECFF).withValues(alpha: pulse);
      dotPaint.maskFilter = MaskFilter.blur(BlurStyle.normal, shortest * 0.014);
      canvas.drawCircle(dot, shortest * (0.011 + 0.005 * pulse), dotPaint);
    }

    final corePaint = Paint()
      ..color = const Color(0xFFE9FCFF).withValues(alpha: 0.78)
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
