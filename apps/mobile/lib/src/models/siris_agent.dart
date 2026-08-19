class SirisAgentMessage {
  const SirisAgentMessage({required this.role, required this.content});

  final String role; // 'user' | 'assistant'
  final String content;

  Map<String, dynamic> toJson() => {'role': role, 'content': content};
}

class SirisAgentReply {
  const SirisAgentReply({
    required this.answer,
    required this.toolsUsed,
    required this.available,
  });

  factory SirisAgentReply.fromJson(Map<String, dynamic> json) => SirisAgentReply(
        answer: json['answer'] as String,
        toolsUsed: (json['tools_used'] as List<dynamic>)
            .whereType<String>()
            .toList(growable: false),
        available: json['available'] as bool,
      );

  final String answer;
  final List<String> toolsUsed;
  final bool available;
}
