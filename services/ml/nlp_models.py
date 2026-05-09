"""Multi-task BERT for emotion + dialogue act (matches NLP_main main_2.ipynb)."""

from __future__ import annotations

import torch
import torch.nn as nn
from transformers import BertConfig, BertModel


class MultiTaskBert(nn.Module):
    def __init__(self, config: BertConfig):
        super().__init__()
        self.config = config
        self.bert = BertModel(config)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        self.act_classifier = nn.Linear(config.hidden_size, config.num_labels_act)
        self.emotion_classifier = nn.Linear(config.hidden_size, config.num_labels_emotion)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        token_type_ids: torch.Tensor | None = None,
        act_labels: torch.Tensor | None = None,
        emotion_labels: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )
        pooled_output = outputs.pooler_output
        pooled_output = self.dropout(pooled_output)
        act_logits = self.act_classifier(pooled_output)
        emotion_logits = self.emotion_classifier(pooled_output)
        return act_logits, emotion_logits


def build_multitask_bert_from_checkpoint(
    *,
    state_dict: dict[str, torch.Tensor],
    pretrained_name: str = "bert-base-uncased",
    device: torch.device,
) -> tuple[MultiTaskBert, BertConfig]:
    """Infer label counts from classifier weights and load state_dict."""
    wa = state_dict["act_classifier.weight"]
    we = state_dict["emotion_classifier.weight"]
    n_act, n_emotion = int(wa.shape[0]), int(we.shape[0])
    config = BertConfig.from_pretrained(pretrained_name)
    config.num_labels_act = n_act
    config.num_labels_emotion = n_emotion
    model = MultiTaskBert(config).to(device)
    model.load_state_dict(state_dict)
    model.eval()
    return model, config
