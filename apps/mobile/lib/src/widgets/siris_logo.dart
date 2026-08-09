import 'dart:math' as math;

import 'package:flutter/material.dart';

/// SirisOS hero branding matching the approved red angular S / silver OS lockup.
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
    _controller = AnimationController(vsync: this, duration: const Duration(seconds: 8))..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final width = widget.showWordmark ? widget.size * 2.25 : widget.size;
    return Semantics(
      label: 'SirisOS',
      image: true,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          final pulse = .5 + .5 * math.sin(_controller.value * math.pi * 2);
          return SizedBox(
            width: width,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: width,
                  height: width * .94,
                  child: CustomPaint(
                    painter: _HeroPainter(progress: _controller.value, pulse: pulse),
                  ),
                ),
                if (widget.showWordmark) ...[
                  SizedBox(height: widget.size * .12),
                  _Wordmark(baseSize: widget.size),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

class _HeroPainter extends CustomPainter {
  const _HeroPainter({required this.progress, required this.pulse});
  final double progress;
  final double pulse;

  Path _sPath(Size s) {
    final w = s.width, h = s.height;
    // Deliberately angular double-ribbon S: broad horizontal caps and a sharp
    // centre crossover, matching the approved SirisOS artwork rather than a
    // conventional rounded letter S.
    return Path()
      ..moveTo(w * .80, h * .16)
      ..lineTo(w * .43, h * .16)
      ..cubicTo(w * .27, h * .16, w * .18, h * .23, w * .18, h * .34)
      ..cubicTo(w * .18, h * .43, w * .25, h * .48, w * .39, h * .53)
      ..lineTo(w * .58, h * .60)
      ..cubicTo(w * .65, h * .63, w * .68, h * .67, w * .68, h * .72)
      ..cubicTo(w * .68, h * .80, w * .60, h * .84, w * .47, h * .84)
      ..lineTo(w * .20, h * .84)
      ..lineTo(w * .31, h * .73)
      ..lineTo(w * .49, h * .73)
      ..cubicTo(w * .54, h * .73, w * .56, h * .71, w * .56, h * .68)
      ..cubicTo(w * .56, h * .65, w * .53, h * .63, w * .47, h * .61)
      ..lineTo(w * .30, h * .55)
      ..cubicTo(w * .13, h * .49, w * .07, h * .41, w * .07, h * .31)
      ..cubicTo(w * .07, h * .15, w * .23, h * .06, w * .43, h * .06)
      ..lineTo(w * .91, h * .06)
      ..close();
  }

  @override
  void paint(Canvas canvas, Size size) {
    // Keep the ring behind the S only. Reserve the lower 20% for separator+OS.
    final centre = Offset(size.width * .5, size.height * .40);
    final ringRadius = size.width * .405;

    final aura = Paint()
      ..shader = RadialGradient(colors: [
        const Color(0xFFFF1027).withValues(alpha: .16 + .07 * pulse),
        const Color(0xFF700008).withValues(alpha: .07),
        Colors.transparent,
      ], stops: const [0, .58, 1]).createShader(
        Rect.fromCircle(center: centre, radius: ringRadius * 1.25),
      );
    canvas.drawCircle(centre, ringRadius * 1.18, aura);

    canvas.drawCircle(
      centre,
      ringRadius,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = size.width * .020
        ..color = const Color(0xFFFF172C).withValues(alpha: .25 + .10 * pulse)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * .022),
    );
    canvas.drawCircle(
      centre,
      ringRadius,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = size.width * .006
        ..color = const Color(0xFFFF3445).withValues(alpha: .92),
    );

    // Draw the S in a clipped upper region so it never collides with OS.
    canvas.save();
    canvas.clipRect(Rect.fromLTWH(0, 0, size.width, size.height * .76));
    final path = _sPath(Size(size.width, size.height * .76));
    final bounds = path.getBounds();
    canvas.drawPath(
      path,
      Paint()
        ..color = const Color(0xFFFF1027).withValues(alpha: .38)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * .032),
    );
    canvas.drawPath(
      path,
      Paint()..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFFFF5260), Color(0xFFFF132A), Color(0xFFC40016), Color(0xFF690008)],
        stops: [0, .27, .68, 1],
      ).createShader(bounds),
    );
    canvas.drawPath(
      path,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = size.width * .006
        ..color = const Color(0xFFFF7380),
    );
    canvas.restore();

    // Separator is visually isolated from both S and OS.
    final sepY = size.height * .755;
    final sepRect = Rect.fromLTWH(size.width * .20, sepY, size.width * .60, size.width * .008);
    canvas.drawRect(
      sepRect.inflate(size.width * .020),
      Paint()
        ..color = const Color(0xFFFF1027).withValues(alpha: .35)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * .020),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(sepRect, const Radius.circular(20)),
      Paint()..color = const Color(0xFFFF4656),
    );

    final os = TextPainter(
      textDirection: TextDirection.ltr,
      textAlign: TextAlign.center,
      text: TextSpan(
        text: 'OS',
        style: TextStyle(
          fontSize: size.width * .185,
          fontWeight: FontWeight.w800,
          letterSpacing: size.width * .020,
          foreground: Paint()..shader = const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFFFFFFFF), Color(0xFFE9E9EB), Color(0xFF85878D), Color(0xFFF1F1F2)],
            stops: [0, .32, .72, 1],
          ).createShader(Rect.fromLTWH(0, 0, size.width, size.height)),
          shadows: const [Shadow(color: Color(0xDD000000), blurRadius: 7, offset: Offset(0, 3))],
        ),
      ),
    )..layout();
    os.paint(canvas, Offset((size.width - os.width) / 2, size.height * .785));

    // Sparse particles remain outside the main silhouette.
    final sparkle = Paint();
    for (var i = 0; i < 16; i++) {
      final a = progress * math.pi * 2 + i * 1.31;
      final r = ringRadius * (.97 + .06 * math.sin(i * 1.9));
      final p = centre + Offset(math.cos(a), math.sin(a)) * r;
      sparkle
        ..color = const Color(0xFFFF2638).withValues(alpha: .10 + .32 * (.5 + .5 * math.sin(a * 2.2)))
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * .003);
      canvas.drawCircle(p, size.width * .0035, sparkle);
    }
  }

  @override
  bool shouldRepaint(covariant _HeroPainter oldDelegate) =>
      oldDelegate.progress != progress || oldDelegate.pulse != pulse;
}

class _Wordmark extends StatelessWidget {
  const _Wordmark({required this.baseSize});
  final double baseSize;

  @override
  Widget build(BuildContext context) => RichText(
    textAlign: TextAlign.center,
    text: TextSpan(
      style: TextStyle(
        fontSize: math.max(14, baseSize * .30),
        fontWeight: FontWeight.w700,
        letterSpacing: baseSize * .13,
        height: 1,
      ),
      children: const [
        TextSpan(text: 'SIRIS', style: TextStyle(color: Color(0xFFE4E4E7))),
        TextSpan(text: 'OS', style: TextStyle(color: Color(0xFFFF2638))),
      ],
    ),
  );
}
