window.APP_CONFIG = {
  // Replace with your hosted S3/CloudFront dataset URL in deployment.
  // For local testing with static file servers, this can stay relative.
  datasetUrl: "./dataset.json",
  // Paginated topic outputs. {page} is replaced with the page number at fetch time.
  topicsIndexUrl: "./topics_index.json",
  topicsPageUrlTemplate: "./topics/page_{page}.json",
  // API Gateway (or similar) URL in front of backend.src.admin_handler.handler
  adminApiUrl: "",
};
