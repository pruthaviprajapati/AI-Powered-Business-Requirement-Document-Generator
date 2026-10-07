# Requirement classifier

ReqAI uses the trained local DistilBERT model at `models/distilbert_requirement_classifier/` to classify extracted requirement candidates. Classification writes `category`, `ml_confidence`, `processing_status`, and `classified_at` to each candidate.

The reported evaluation accuracy is approximately **35%**. This is an honest limitation of the available labelled data, not a deployment-quality accuracy claim. More representative, consistently labelled requirements and a held-out evaluation set are needed before relying on classifications without review.
