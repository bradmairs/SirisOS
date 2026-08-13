class AskSirisAnswer {
  const AskSirisAnswer({
    required this.question,
    required this.understood,
    required this.answer,
    required this.synthesizedAnswer,
    required this.suggestions,
  });

  factory AskSirisAnswer.fromJson(Map<String, dynamic> json) =>
      AskSirisAnswer(
        question: json['question'] as String,
        understood: json['understood'] as bool,
        answer: json['answer'] as String,
        synthesizedAnswer: json['synthesized_answer'] as String?,
        suggestions: (json['suggestions'] as List<dynamic>)
            .whereType<String>()
            .toList(growable: false),
      );

  final String question;
  final bool understood;
  final String answer;
  final String? synthesizedAnswer;
  final List<String> suggestions;
}
