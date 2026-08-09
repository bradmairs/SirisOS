import 'dart:math' as math;

import 'package:flutter/material.dart';

/// SirisOS hero branding.
///
/// Drawn in Flutter rather than relying on a cropped raster asset so the
/// angular, beveled Siris S remains crisp at every screen size.
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
    final width = widget.showWordmark ? widget.size * 2.25 : widget.size;

    return Semantics(
      label: 'SirisOS',
      image: true,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          final pulse = 0.5 + 0.5 * math.sin(_controller.value * math.pi * 2);
          return SizedBox(
            width: width,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: width,
                  height: width * 1.10,
                  child: CustomPaint(
                    painter: _SirisHeroPainter(
                      progress: _controller.value,
                      pulse: pulse,
                    ),
                  ),
                ),
                if (widget.showWordmark) ...[
                  SizedBox(height: widget.size * 0.04),
                  _SirisOsWordmark(baseSize: widget.size),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

class _SirisHeroPainter extends CustomPainter {
  const _SirisHeroPainter({required this.progress, required this.pulse});

  final double progress;
  final double pulse;

  Path _sPath(Size s) {
    final w = s.width;
    final h = s.height;
    return Path()
      ..moveTo(w * .73, h * .18)
      ..lineTo(w * .43, h * .18)
      ..cubicTo(w * .27, h * .18, w * .19, h * .25, w * .19, h * .34)
      ..cubicTo(w * .19, h * .42, w * .27, h * .46, w * .40, h * .50)
      ..lineTo(w * .57, h * .56)
      ..cubicTo(w * .66, h * .59, w * .70, h * .64, w * .70, h * .70)
      ..cubicTo(w * .70, h * .78, w * .62, h * .82, w * .49, h * .82)
      ..lineTo(w * .22, h * .82)
      ..lineTo(w * .32, h * .72)
      ..lineTo(w * .50, h * .72)
      ..cubicTo(w * .55, h * .72, w * .58, h * .70, w * .58, h * .67)
      ..cubicTo(w * .58, h * .64, w * .55, h * .62, w * .49, h * .60)
      ..lineTo(w * .31, h * .54)
      ..cubicTo(w * .14, h * .48, w * .08, h * .40, w * .08, h * .31)
      ..cubicTo(w * .08, h * .16, w * .23, h * .08, w * .43, h * .08)
      ..lineTo(w * .83, h * .08)
      ..close();
  }

  @override
  void paint(Canvas canvas, Size size) {
    final centre = Offset(size.width * .5, size.height * .47);
    final ringRadius = size.width * .46;

    final aura = Paint()
      ..shader = RadialGradient(
        colors: [
          const Color(0xFFFF1027).withValues(alpha: .17 + .08 * pulse),
          const Color(0xFF6F000A).withValues(alpha: .08),
          Colors.transparent,
        ],
      ).createShader(Rect.fromCircle(center: centre, radius: ringRadius * 1.18));
    canvas.drawCircle(centre, ringRadius * 1.16, aura);

    final ringGlow = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.width * .018
      ..color = const Color(0xFFFF1D32).withValues(alpha: .24 + .12 * pulse)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * .025);
    canvas.drawCircle(centre, ringRadius, ringGlow);

    final ring = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.width * .006
      ..color = const Color(0xFFFF3141).withValues(alpha: .90);
    canvas.drawCircle(centre, ringRadius, ring);

    final sPath = _sPath(size);
    canvas.drawPath(
      sPath,
      Paint()
        ..color = const Color(0xFFFF1027).withValues(alpha: .40)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * .035),
    );

    final bounds = sPath.getBounds();
    final fill = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          Color(0xFFFF4A58),
          Color(0xFFFF1027),
          Color(0xFFB50012),
          Color(0xFF6D0008),
        ],
        stops: [0, .28, .67, 1],
      ).createShader(bounds);
    canvas.drawPath(sPath, fill);

    canvas.drawPath(
      sPath,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = size.width * .007
        ..color = const Color(0xFFFF6975),
    );

    final lowerShade = Path()
      ..moveTo(size.width * .22, size.height * .82)
      ..lineTo(size.width * .49, size.height * .82)
      ..cubicTo(size.width * .62, size.height * .82, size.width * .70, size.height * .78, size.width * .70, size.height * .70)
      ..lineTo(size.width * .58, size.height * .67)
      ..cubicTo(size.width * .58, size.height * .70, size.width * .55, size.height * .72, size.width * .50, size.height * .72)
      ..lineTo(size.width * .32, size.height * .72)
      ..close();
    canvas.drawPath(
      lowerShade,
      Paint()..color = const Color(0xFF720008).withValues(alpha: .55),
    );

    final separatorY = size.height * .87;
    final separator = Rect.fromLTWH(
      size.width * .20,
      separatorY,
      size.width * .60,
      size.width * .008,
    );
    canvas.drawRect(
      separator.inflate(size.width * .018),
      Paint()
        ..color = const Color(0xFFFF1027).withValues(alpha: .38)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * .022),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(separator, const Radius.circular(20)),
      Paint()..color = const Color(0xFFFF4050),
    );

    final osPainter = TextPainter(
      textDirection: TextDirection.ltr,
      text: TextSpan(
        text: 'OS',
        style: TextStyle(
          fontSize: size.width * .19,
          fontWeight: FontWeight.w700,
          letterSpacing: size.width * .025,
          foreground: Paint()
            ..shader = const LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xFFFFFFFF), Color(0xFFBFC1C6), Color(0xFF5E6065), Color(0xFFE6E6E8)],
              stops: [0, .32, .70, 1],
            ).createShader(Rect.fromLTWH(0, 0, size.width, size.height)),
          shadows: const [
            Shadow(color: Color(0xCC000000), blurRadius: 8, offset: Offset(0, 4)),
          ],
        ),
      ),
    )..layout();
    osPainter.paint(
      canvas,
      Offset((size.width - osPainter.width) / 2, size.height * .895),
    );

    final sparklePaint = Paint()..color = const Color(0xFFFF2638);
    for (var i = 0; i < 20; i++) {
      final angle = progress * math.pi * 2 + i * .91;
      final radius = ringRadius * (.92 + .08 * math.sin(i * 1.7));
      final p = centre + Offset(math.cos(angle), math.sin(angle)) * radius;
      sparklePaint.color = const Color(0xFFFF2638).withValues(
        alpha: .12 + .38 * (0.5 + 0.5 * math.sin(angle * 2.3)),
      );
      canvas.drawCircle(p, size.width * .004, sparklePaint);
    }
  }

  @override
  bool shouldRepaint(covariant _SirisHeroPainter oldDelegate) =>
      oldDelegate.progress != progress || oldDelegate.pulse != pulse;
}

class _SirisOsWordmark extends StatelessWidget {
  const _SirisOsWordmark({required this.baseSize});

  final double baseSize;

  @override
  Widget build(BuildContext context) => RichText(
        text: TextSpan(
          style: TextStyle(
            fontSize: math.max(14.0, baseSize * .30),
            fontWeight: FontWeight.w700,
            letterSpacing: baseSize * .13,
            shadows: const [
              Shadow(color: Color(0x66000000), blurRadius: 5, offset: Offset(0, 2)),
            ],
          ),
          children: const [
            TextSpan(text: 'SIRIS', style: TextStyle(color: Color(0xFFE3E3E6))),
            TextSpan(text: 'OS', style: TextStyle(color: Color(0xFFFF2638))),
          ],
        ),
      );
}
