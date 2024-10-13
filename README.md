# 🔨 Hammer

Hammer is a multi-modal multi-task feed-forward neural network that predicts the pathways, classes, and superclasses of natural products based on their molecular structure and physicochemical properties. The classifier leverages a diverse set of molecular fingerprints and descriptors to capture the unique features of natural products and enable accurate predictions across multiple tasks.

The model can be beheaded (remove the output layers) and used either as a feature extractor or as a pre-trained model for transfer learning on other tasks. This package provides also tooling to extract and visualize all of the features used in the model, which can be used to train other models or to perform downstream analyses. **If you intend to use this model for transfer learning, pay attention to not include in your test set SMILEs used for training this model to avoid biasing your evaluations!**

## Installation

This library will be available to install via pip, but for now you can install it by cloning the repository and running the following command:

```bash
pip install .
```

## Feature visualization

To visualize the features used in the model using PCA and t-SNE, you can run the following command:

```bash
hammer visualize --verbose --dataset NPC --output-directory "data_visualizations" --image-format "png"
```

This will generate a set of plots that show the distribution of the features used in the model. The plots will be saved in the `data_visualizations` directory in the `png` format. You can change the output directory and image format by changing the `--output-directory` and `--image-format` arguments, respectively. The resulting plots will look like the following (this one illustrates the t-SNE and PCA decomposition of the Topological Torsion 1024 bits):

[![Topological Torsion (1024 bits)](https://github.com/LucaCappelletti94/hammer/blob/main/data_visualizations/Topological%20Torsion%20(1024b).png?raw=true)](https://github.com/LucaCappelletti94/hammer/tree/main/data_visualizations)

It is also possible to visualize specific feature sets, for example the MAP4 features, by using the `--include-map4` argument:

```bash
hammer visualize --verbose\
    --dataset NPC\
    --include-map4\
    --output-directory "data_visualizations"\
    --image-format "png"
```

## Feature sets evaluation

To evaluate the feature sets used in the model, you can run the following command. This will perform a 10-fold cross-validation evaluation of the feature sets. The performance for all holdouts and all considered features will be saved in the `feature_sets_evaluation.csv` file, while the barplots will be saved in the `feature_sets_evaluation_barplots` directory.

The dataset is split using first a stratified split by the rarest class, then subsequently `holdouts` number of stratified Monte Carlo splits into sub-training and validation. **The test set is not touched during this evaluation process, as we will use it to evaluate the model over the selected feature set.**

The model used for these evaluations is the same Hammer model that is used for the predictions, changing only the number of input feature sets.

```bash
hammer feature-sets-evaluation \
    --verbose \
    --holdouts 5 \
    --dataset NPC \
    --test-size 0.2 \
    --validation-size 0.2 \
    --performance-path "feature_sets_evaluation.csv" \
    --training-directory "feature_selection_training" \
    --barplot-directory "feature_sets_evaluation_barplots"
```

Executing this command will generate the barplots [you can find in this directory](https://github.com/LucaCappelletti94/hammer/tree/main/feature_sets_evaluation_barplots). In the following barplot, you will find the AUPRC for each class, for validation, test a, for each feature set, averaged over all holdouts:

[![AUPRC barplot](https://github.com/LucaCappelletti94/hammer/blob/main/feature_sets_evaluation_barplots/class_auprc_feature_sets.png?raw=true)](https://github.com/LucaCappelletti94/hammer/tree/main/feature_sets_evaluation_barplots)


It is also possible to run the `feature-sets-evaluation` on a subset of features:

```bash
hammer feature-sets-evaluation \
    --verbose \
    --holdouts 5 \
    --dataset NPC \
    --include-map4 \
    --test-size 0.2 \
    --validation-size 0.2 \
    --performance-path "map4_feature_evaluation.csv" \
    --training-directory "map4_feature_training" \
    --barplot-directory "map4_feature_evaluation"
```

## DAG Coverage

One of the goals of this project is to, over time and with the help of the community, increase the overall number of pathways, superclasses, and classes that the model can predict. The model employs as a form of static attention a DAG that harmonizes the predictions of the different tasks. At this time, the dataset we are using **DOES NOT** cover all of the combinations of pathways, superclasses and classes that the DAG allows for. We aim to increase the coverage of the DAG over time, and we welcome contributions to the dataset that can help us achieve this goal. *We are starting out from the dataset made available by [NP Classifier](https://github.com/mwang87/NP-Classifier).*

You can compute a summary of the coverage of the DAG using the following command:

```bash
hammer dag-coverage --dataset NPC --verbose
```

At the time of writing, the coverage of the DAG is as follows:

| Layer        |   Coverage |
|:-------------|-----------:|
| pathways     |   1        |
| superclasses |   0.922078 |
| classes      |   0.941092 |
| DAG          |   0.822319 |
