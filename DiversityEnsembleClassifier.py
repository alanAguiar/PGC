from sklearn.neighbors import KNeighborsClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn import datasets
from sklearn.metrics import accuracy_score
from sklearn.model_selection import KFold
import math
import numpy as np
import scipy.stats
import copy
import random
import operator
import time

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

class Chromossome:
    def __init__(self, algorithm, random_state=None, njobs=1, **hyperparameter_range):
        self.hyperparameter_range = hyperparameter_range
        try:
            self.classifier = algorithm(random_state=random_state)
        except:
            self.classifier = algorithm()
        try: 
            self.classifier.set_params(njobs=njobs)
        except:
            pass
        self.mutate()
        self.fitness = 0
        
    def fit(self, X, y):
        is_fitted = True
        self.classifier.fit(X, y)
        
    def predict(self, X):
        return self.classifier.predict(X)
        
    def mutate(self, n_positions=None):
        param = {}        
        if not n_positions or n_positions>len(self.hyperparameter_range):
            n_positions = len(self.hyperparameter_range)
        mutation_positions = random.sample(range(0, len(self.hyperparameter_range)), n_positions)
        i = 0
        for hyperparameter, h_range in self.hyperparameter_range.items():
            if i in mutation_positions:
                if isinstance(h_range[0], str):
                    param[hyperparameter] = random.choice(h_range)
                elif isinstance(h_range[0], float):
                    param[hyperparameter] = random.uniform(h_range[0], h_range[1]+1)
                else:
                    param[hyperparameter] = random.randint(h_range[0], h_range[1]+1)
            i+= 1
        
        self.classifier.set_params(**param)

class DiversityEnsembleClassifier:
    def __init__(self, algorithms, population_size = 100, max_epochs = 100, random_state=None, njobs=1):
        self.population_size = population_size
        self.max_epochs = max_epochs
        self.population = []
        self.random_state = random_state
        random.seed(self.random_state)
        for algorithm, hyperparameters in algorithms.items():
            for i in range(0, math.ceil(population_size/len(algorithms.keys()))):
                self.population.append(Chromossome(algorithm, njobs=njobs, random_state=random_state, **hyperparameters))
    
    def generate_offspring(self, parents, children):
        if not parents:
            parents = [x for x in range(0, self.population_size)]
            children = [x for x in range(self.population_size, 2*self.population_size)]
        for i in range(0, self.population_size):
            new_chromossome = copy.deepcopy(self.population[parents[i]])
            new_chromossome.mutate(1)
            try:
                self.population[children[i]] = new_chromossome
            except:
                self.population.append(new_chromossome)
            
    def fit_predict_population(self, not_fitted, predictions, kfolds, X, y):
        for i in not_fitted:
            chromossome = self.population[i]
            for train, val in kfolds.split(X):
                chromossome.fit(X[train], y[train])
                predictions[i][val] = np.equal(chromossome.predict(X[val]), y[val])
        return predictions 
    
    def diversity_selection(self, predictions):
        distances = np.zeros(2*self.population_size)
        pop_fitness = predictions.sum(axis=1)
        target_chromossome = np.argmin(pop_fitness)
        selected = [target_chromossome]
        diversity  = np.zeros(2*self.population_size)
        for i in range(0, self.population_size-1):
            distances[target_chromossome] = float('-inf')
            d_i = np.logical_xor(predictions, predictions[target_chromossome]).sum(axis=1)
            distances += d_i
            diversity += d_i/predictions.shape[1]
            target_chromossome = np.argmax(distances)
            selected.append(target_chromossome)
            self.population[target_chromossome].fitness = pop_fitness[target_chromossome]
        
        return selected, (diversity[selected]/(self.population_size-1)).mean()
    
    def fit(self, X, y):
        print('Starting genetic algorithm...')        
        kf = KFold(n_splits=5, random_state=self.random_state)
        start_time = int(round(time.time() * 1000))
        random.seed(self.random_state)
        
        selected, not_selected = [], []
        predictions = np.empty([2*self.population_size, y.shape[0]])
                                                            
        for epoch in range(self.max_epochs):   
            print('-' * 60)
            print('Epoch', epoch)            
            print('-' * 60)
            
            not_selected = np.setdiff1d([x for x in range(0, 2*self.population_size)], selected)
            
            print('Generating offspring...', end='')
            aux = int(round(time.time() * 1000))
            self.generate_offspring(selected, not_selected)             
            print('done in',int(round(time.time() * 1000)) - aux, 'ms')
            
            print('Fitting and predicting population...', end='')
            aux = int(round(time.time() * 1000))
            predictions = self.fit_predict_population(not_selected, predictions, kf, X, y)  
            print('done in',int(round(time.time() * 1000)) - aux, 'ms')
                        
            print('Applying diversity selection...', end='')
            aux = int(round(time.time() * 1000))
            selected, diversity = self.diversity_selection(predictions) 
            print('done in',int(round(time.time() * 1000)) - aux, 'ms')
            
            print('New population diversity measure:', diversity)
        
        print('-' * 60, '\nFinished genetic algorithm in ', int(round(time.time() * 1000)) - start_time, 'ms')
        
        self.population = [self.population[x] for x in selected]                            
        for chromossome in self.population:
            chromossome.fit(X, y)
            
    def predict(self, X):
        predictions = np.empty((self.population_size, len(X)))
        y = np.empty(len(X))
        for chromossome in range(0, self.population_size):
            predictions[chromossome] = self.population[chromossome].predict(X)
        for i in range(0, len(X)):
            pred = {}
            for j in range(0, self.population_size):
                if predictions[j][i] in pred:
                    pred[predictions[j][i]] += self.population[j].fitness
                else: 
                    pred[predictions[j][i]]  = self.population[j].fitness
            y[i] = max(pred.items(), key=operator.itemgetter(1))[0]
        return y